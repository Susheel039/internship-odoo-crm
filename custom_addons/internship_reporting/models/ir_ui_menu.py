from odoo import api, models

VIEWER_GROUP = "internship_reporting.group_dashboard_viewer"
# Any of these gives the user the normal menus as well.
FULL_ACCESS_GROUPS = (
    "base.group_system",
    "base.group_erp_manager",
    "internship_base.group_platform_administrator",
    "internship_base.group_university_administrator",
    "internship_base.group_university_staff",
    "internship_base.group_company_manager",
    "internship_base.group_student",
    "internship_base.group_line_manager",
    "internship_base.group_crm_agent",
    "sales_team.group_sale_salesman",
)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _is_dashboard_viewer_only(self):
        user = self.env.user
        return user.has_group(VIEWER_GROUP) and not any(user.has_group(group) for group in FULL_ACCESS_GROUPS)

    def _visible_menu_ids(self, debug=False):
        """Dashboard viewers see INTERNTION > Dashboard and nothing else."""
        visible = super()._visible_menu_ids(debug)
        if not self._is_dashboard_viewer_only():
            return visible
        allowed = {
            self.env.ref("internship_base.menu_internship_root").id,
            self.env.ref("internship_reporting.menu_internship_dashboard").id,
        }
        return frozenset(visible & allowed) if isinstance(visible, frozenset) else set(visible) & allowed
