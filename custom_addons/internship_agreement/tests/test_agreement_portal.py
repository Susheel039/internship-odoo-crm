from odoo.tests import HttpCase, tagged

from odoo.addons.internship_placement.tests.common import PlacementCommon

from .test_agreement import SIGNATURE


@tagged("post_install", "-at_install")
class TestAgreementPortal(PlacementCommon, HttpCase):
    def test_public_signing_routes(self):
        placement = self._submit_form(self._accepted_placement())
        self._review(placement, "approve")
        agreement = placement.agreement_id
        signer = agreement.current_signer_id
        token = signer.sudo().access_token
        base = f"/internship/agreement/{agreement.id}"
        self.authenticate(None, None)  # anonymous visitor, but bound to the test database

        self.assertEqual(self.url_open(f"{base}/sign/not-a-valid-token").status_code, 404)
        page = self.url_open(f"{base}/sign/{token}")
        self.assertEqual(page.status_code, 200, page.text[:3000])
        self.assertIn(agreement.name, page.text)
        self.assertEqual(self.url_open(f"{base}/document/{token}").status_code, 200)

        result = self.make_jsonrpc_request(
            f"{base}/sign/{token}/submit", {"name": "Line Manager", "signature": SIGNATURE}
        )
        self.assertTrue(result.get("force_refresh"), result)
        self.assertEqual(signer.state, "signed")
        self.assertTrue(signer.signed_ip)
        self.assertEqual(agreement.state, "sent_student")

        again = self.make_jsonrpc_request(
            f"{base}/sign/{token}/submit", {"name": "Line Manager", "signature": SIGNATURE}
        )
        self.assertIn("error", again, "a signer cannot sign twice")
