from odoo import api, fields, models

# Placement stage -> student lifecycle status
STAGE_LIFECYCLE = {
    "form_requested": "offered",
    "under_review": "offered",
    "more_docs": "offered",
    "meeting": "offered",
    "agreement": "offered",
    "approved": "approved",
    "active": "in_internship",
    "on_hold": "in_internship",
    "completion": "in_internship",
    "completed": "completed",
    "failed": "failed",
    "terminated": "withdrawn",
    "rejected": "searching",
}


class InternshipStudent(models.Model):
    _inherit = "internship.student"

    placement_ids = fields.One2many("internship.placement", "student_id", string="Placement")
    active_placement_id = fields.Many2one("internship.placement", compute="_compute_active_placement_id")
    placement_count = fields.Integer(compute="_compute_active_placement_id")

    @api.depends("placement_ids.is_closed", "placement_ids.active")
    def _compute_active_placement_id(self):
        for student in self:
            student.active_placement_id = student.placement_ids.filtered(lambda p: p.active and not p.is_closed)[:1]
            student.placement_count = len(student.placement_ids)

    @api.depends("placement_ids.stage_code", "placement_ids.active")
    def _compute_lifecycle_status(self):
        return super()._compute_lifecycle_status()

    def _lifecycle_from_applications(self):
        self.ensure_one()
        placements = self.placement_ids.filtered("active").sorted("id", reverse=True)
        current = placements.filtered(lambda p: not p.is_closed)[:1] or placements[:1]
        if current:
            status = STAGE_LIFECYCLE.get(current.stage_code)
            if status == "searching":
                # Rejected by the university: back to searching unless other applications are live.
                return (
                    super()._lifecycle_from_applications()
                    if self.application_ids.filtered(
                        lambda a: a.status in ("submitted", "under_review", "interview", "offered")
                    )
                    else "searching"
                )
            if status:
                return status
        return super()._lifecycle_from_applications()

    @api.depends("placement_ids.actual_end", "placement_ids.planned_end")
    def _compute_retention_until(self):
        return super()._compute_retention_until()

    def _retention_anchor_date(self):
        ends = [d for d in self.placement_ids.mapped("actual_end") + self.placement_ids.mapped("planned_end") if d]
        return max(ends) if ends else super()._retention_anchor_date()

    def action_view_placements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Placements"),
            "res_model": "internship.placement",
            "view_mode": "list,form",
            "domain": [("student_id", "=", self.id)],
            "context": {"default_student_id": self.id},
        }
