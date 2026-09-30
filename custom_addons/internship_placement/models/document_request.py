from odoo import api, fields, models

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once


class InternshipDocumentRequest(models.Model):
    _name = "internship.document.request"
    _description = "Document Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "internship.placement.link.mixin"]
    _order = "requested_date desc, id desc"

    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    round_no = fields.Integer(string="Round", default=1)
    requested_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, string="Requested By")
    requested_date = fields.Date(default=fields.Date.context_today, tracking=True)
    requested_from = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("both", "Student and company")],
        default="both",
        required=True,
    )
    due_date = fields.Date(tracking=True, index=True)
    state = fields.Selection(
        [("open", "Open"), ("partial", "Partially received"), ("complete", "Complete"), ("overdue", "Overdue")],
        compute="_compute_state",
        store=True,
        index=True,
        tracking=True,
    )
    completed_date = fields.Date(readonly=True, copy=False)
    reminder_count = fields.Integer(copy=False)
    last_reminder_date = fields.Date(copy=False)
    line_ids = fields.One2many("internship.document.request.line", "request_id", string="Documents", copy=True)
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("internship.document.request") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.accepted", "line_ids.attachment_id", "line_ids.mandatory", "due_date")
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for request in self:
            mandatory = request.line_ids.filtered("mandatory")
            if (
                request.line_ids
                and all(mandatory.mapped("accepted"))
                and (mandatory or all(request.line_ids.mapped("accepted")))
            ):
                request.state = "complete"
            elif request.due_date and request.due_date < today:
                request.state = "overdue"
            elif request.line_ids.filtered(lambda line: line.attachment_id or line.accepted):
                request.state = "partial"
            else:
                request.state = "open"

    def _check_completion(self):
        for request in self.filtered(lambda r: r.state == "complete" and not r.completed_date):
            request.completed_date = fields.Date.context_today(self)
            request.message_post(body=self.env._("All mandatory documents accepted."))
            request.placement_id._on_document_request_complete(request)
        return True

    def action_send(self):
        template = self.env.ref("internship_placement.mail_template_document_request", raise_if_not_found=False)
        for request in self:
            if template:
                template.send_mail(request.id)
            owner = request.placement_id._company_owner() if request.requested_from == "company" else None
            schedule_activity_once(
                request,
                owner or request.placement_id.user_id or default_coordinator(self.env),
                self.env._("Upload the requested documents"),
                deadline=request.due_date,
            )
        return True

    @api.model
    def _cron_reminders(self):
        """Refresh overdue state and chase open requests every 3 days, at most 3 times."""
        today = fields.Date.context_today(self)
        pending = self.search([("state", "in", ("open", "partial", "overdue"))])
        if pending:
            self.env.add_to_compute(self._fields["state"], pending)
            pending.flush_recordset(["state"])
        template = self.env.ref("internship_placement.mail_template_document_request", raise_if_not_found=False)
        for request in pending.filtered(lambda r: r.due_date and r.due_date <= today and r.reminder_count < 3):
            if request.last_reminder_date and (today - request.last_reminder_date).days < 3:
                continue
            if template:
                template.send_mail(request.id)
            request.write({"reminder_count": request.reminder_count + 1, "last_reminder_date": today})
        return True
