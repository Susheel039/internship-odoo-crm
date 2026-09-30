from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

RISK_LABELS = {"green": "On track", "amber": "Needs attention", "red": "At risk"}
PHASE_LABELS = {"1": "Admission", "2": "Monitoring", "3": "Completion"}


class InternshipDashboard(models.AbstractModel):
    """Data for the Internship CRM dashboard (client action `internship_dashboard`).

    One call returns KPI cards, chart series and short lists. Every series carries the
    model and domain behind it, so clicking a card or chart segment opens those records.
    """

    _name = "internship.dashboard"
    _description = "Internship Dashboard Data"

    @api.model
    def get_dashboard_data(self, university_id=False):
        # Dashboard Viewers have no access to the records themselves: compute the totals with
        # elevated rights and tell the page not to open records.
        can_open = self.env["internship.placement"].has_access("read")
        if not can_open and self.env.user.has_group("internship_reporting.group_dashboard_viewer"):
            self = self.sudo()
        data = self._get_dashboard_data(university_id)
        data["can_open"] = can_open
        return data

    @api.model
    def _get_dashboard_data(self, university_id=False):
        university_id = int(university_id or 0) or False
        placement_scope = [("university_id", "=", university_id)] if university_id else []
        application_scope = [("university_id", "=", university_id)] if university_id else []

        report = self.env["internship.report"].new({"university_id": university_id})
        return {
            "universities": [
                {"id": u.id, "name": u.name} for u in self.env["internship.university"].search([], order="name")
            ],
            "university_id": university_id,
            "kpis": self._kpis(report, placement_scope, application_scope),
            "charts": {
                "placements_by_stage": self._placements_by_stage(placement_scope),
                "placements_by_phase": self._placements_by_phase(placement_scope),
                "risk": self._risk(placement_scope),
                "applications": self._applications(application_scope),
                "leads_by_stage": self._leads_by_stage(),
                "leads_by_source": self._leads_by_source(),
                "attendance_trend": self._attendance_trend(placement_scope),
                "calls_by_week": self._calls_by_week(),
            },
            "at_risk": self._at_risk(placement_scope),
            "callbacks": self._callbacks(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _series(label, model, rows):
        """rows: [(label, value, domain, color?)]"""
        return {
            "label": label,
            "model": model,
            "labels": [row[0] for row in rows],
            "values": [row[1] for row in rows],
            "domains": [row[2] for row in rows],
            "colors": [row[3] if len(row) > 3 else None for row in rows],
        }

    def _selection_labels(self, model, field_name):
        return dict(self.env[model]._fields[field_name]._description_selection(self.env))

    def _kpis(self, report, placement_scope, application_scope):
        Placement = self.env["internship.placement"]
        Lead = self.env["crm.lead"].sudo()
        Call = self.env["internship.call.log"].sudo()
        open_scope = placement_scope + [("is_closed", "=", False)]
        month_start = fields.Date.context_today(self).replace(day=1)
        lead_scope = [("lead_category", "!=", False)]
        return [
            {
                "key": "students",
                "label": self.env._("Students"),
                "value": report.total_students,
                "icon": "fa-graduation-cap",
                "model": "internship.student",
                "domain": [("university_id", "=", report.university_id.id)] if report.university_id else [],
            },
            {
                "key": "applications",
                "label": self.env._("Open applications"),
                "value": self.env["internship.application"].search_count(
                    application_scope + [("status", "in", ("submitted", "under_review", "interview", "offered"))]
                ),
                "icon": "fa-file-text-o",
                "model": "internship.application",
                "domain": application_scope + [("status", "in", ("submitted", "under_review", "interview", "offered"))],
            },
            {
                "key": "in_admission",
                "label": self.env._("In admission"),
                "value": Placement.search_count(open_scope + [("phase", "=", "1")]),
                "icon": "fa-check-square-o",
                "model": "internship.placement",
                "domain": open_scope + [("phase", "=", "1")],
            },
            {
                "key": "active",
                "label": self.env._("On placement"),
                "value": Placement.search_count(placement_scope + [("stage_code", "in", ("active", "on_hold"))]),
                "icon": "fa-briefcase",
                "model": "internship.placement",
                "domain": placement_scope + [("stage_code", "in", ("active", "on_hold"))],
            },
            {
                "key": "at_risk",
                "label": self.env._("At risk"),
                "value": Placement.search_count(open_scope + [("risk_flag", "=", "red")]),
                "icon": "fa-exclamation-triangle",
                "tone": "danger",
                "model": "internship.placement",
                "domain": open_scope + [("risk_flag", "=", "red")],
            },
            {
                "key": "completion_rate",
                "label": self.env._("Completion rate"),
                "value": f"{report.completion_rate:.0f}%",
                "icon": "fa-flag-checkered",
                "tone": "success",
                "model": "internship.placement",
                "domain": placement_scope + [("stage_code", "=", "completed")],
            },
            {
                "key": "hot_leads",
                "label": self.env._("Hot leads"),
                "value": Lead.search_count(lead_scope + [("interest_level", "=", "hot")]),
                "icon": "fa-fire",
                "tone": "warning",
                "model": "crm.lead",
                "domain": lead_scope + [("interest_level", "=", "hot")],
            },
            {
                "key": "calls",
                "label": self.env._("AI calls this month"),
                "value": Call.search_count([("call_datetime", ">=", fields.Datetime.to_datetime(month_start))]),
                "icon": "fa-phone",
                "model": "internship.call.log",
                "domain": [
                    ("call_datetime", ">=", fields.Datetime.to_string(fields.Datetime.to_datetime(month_start)))
                ],
            },
        ]

    def _placements_by_stage(self, scope):
        stages = self.env["internship.placement.stage"].search([])
        counts = dict(
            self.env["internship.placement"]._read_group(scope + [("active", "=", True)], ["stage_id"], ["__count"])
        )
        phase_colors = {"1": "#2E5EAA", "2": "#1F9D8B", "3": "#8E6CC0"}
        rows = []
        for stage in stages:
            color = "#9AA5B1" if stage.is_closed and not stage.is_won else phase_colors.get(stage.phase)
            if stage.is_won:
                color = "#2E9D57"
            rows.append((stage.name, counts.get(stage, 0), scope + [("stage_id", "=", stage.id)], color))
        return self._series(self.env._("Placements"), "internship.placement", rows)

    def _placements_by_phase(self, scope):
        counts = dict(
            self.env["internship.placement"]._read_group(scope + [("is_closed", "=", False)], ["phase"], ["__count"])
        )
        colors = {"1": "#2E5EAA", "2": "#1F9D8B", "3": "#8E6CC0"}
        rows = [
            (
                self.env._(label),
                counts.get(phase, 0),
                scope + [("is_closed", "=", False), ("phase", "=", phase)],
                colors[phase],
            )
            for phase, label in PHASE_LABELS.items()
        ]
        return self._series(self.env._("Open placements"), "internship.placement", rows)

    def _risk(self, scope):
        counts = dict(
            self.env["internship.placement"]._read_group(
                scope + [("is_closed", "=", False)], ["risk_flag"], ["__count"]
            )
        )
        colors = {"green": "#2E9D57", "amber": "#E0A100", "red": "#D64545"}
        rows = [
            (
                self.env._(label),
                counts.get(flag, 0),
                scope + [("is_closed", "=", False), ("risk_flag", "=", flag)],
                colors[flag],
            )
            for flag, label in RISK_LABELS.items()
        ]
        return self._series(self.env._("Risk"), "internship.placement", rows)

    def _applications(self, scope):
        labels = self._selection_labels("internship.application", "status")
        counts = dict(self.env["internship.application"]._read_group(scope, ["status"], ["__count"]))
        rows = [(labels[key], counts.get(key, 0), scope + [("status", "=", key)]) for key in labels]
        return self._series(self.env._("Applications"), "internship.application", rows)

    def _leads_by_stage(self):
        Lead = self.env["crm.lead"].sudo()
        scope = [("lead_category", "!=", False), ("type", "=", "opportunity")]
        groups = Lead._read_group(scope, ["stage_id"], ["__count"], order="stage_id")
        rows = [
            (stage.name or self.env._("No stage"), count, scope + [("stage_id", "=", stage.id)])
            for stage, count in groups
        ]
        return self._series(self.env._("Leads"), "crm.lead", rows)

    def _leads_by_source(self):
        Lead = self.env["crm.lead"].sudo()
        labels = self._selection_labels("crm.lead", "source_channel")
        scope = [("lead_category", "!=", False)]
        counts = dict(Lead._read_group(scope, ["source_channel"], ["__count"]))
        rows = [
            (labels.get(key, self.env._("Unknown")), count, scope + [("source_channel", "=", key)])
            for key, count in counts.items()
            if count
        ]
        return self._series(self.env._("Leads by source"), "crm.lead", rows)

    def _attendance_trend(self, scope):
        today = fields.Date.context_today(self)
        start = (today - relativedelta(months=5)).replace(day=1)
        # Only records the student has submitted count towards the average.
        monthly_scope = [
            ("date_start", ">=", start),
            ("state", "in", ("submitted", "company_approved", "university_reviewed", "flagged")),
            ("days_expected", ">", 0),
        ]
        if scope:
            monthly_scope.append(("placement_id.university_id", "=", scope[0][2]))
        groups = self.env["internship.attendance.monthly"]._read_group(
            monthly_scope, ["date_start:month"], ["attendance_pct:avg", "__count"], order="date_start:month"
        )
        rows = []
        for month, avg, _count in groups:
            month_end = month + relativedelta(months=1)
            rows.append(
                (
                    month.strftime("%b %Y"),
                    round(avg or 0.0, 1),
                    monthly_scope + [("date_start", ">=", month), ("date_start", "<", month_end)],
                )
            )
        series = self._series(self.env._("Average attendance %"), "internship.attendance.monthly", rows)
        series["threshold"] = self.env["internship.program"]._get_rule("tripartite_attendance_pct")
        return series

    def _calls_by_week(self):
        Call = self.env["internship.call.log"].sudo()
        now = fields.Datetime.now()
        start = now - relativedelta(weeks=7)
        groups = Call._read_group(
            [("call_datetime", ">=", start)], ["call_datetime:week"], ["__count"], order="call_datetime:week"
        )
        rows = []
        for week, count in groups:
            week_end = week + relativedelta(weeks=1)
            rows.append(
                (
                    week.strftime("%d %b"),
                    count,
                    [
                        ("call_datetime", ">=", fields.Datetime.to_string(week)),
                        ("call_datetime", "<", fields.Datetime.to_string(week_end)),
                    ],
                )
            )
        return self._series(self.env._("AI calls per week"), "internship.call.log", rows)

    def _at_risk(self, scope):
        placements = self.env["internship.placement"].search(
            scope + [("is_closed", "=", False), ("risk_flag", "in", ("red", "amber"))],
            order="risk_flag desc, id desc",
            limit=6,
        )
        return [
            {
                "id": p.id,
                "name": p.name,
                "student": p.student_id.name,
                "company": p.internship_company_id.name,
                "stage": p.stage_id.name,
                "risk": p.risk_flag,
                "reason": p.risk_reason or "",
            }
            for p in placements
        ]

    def _callbacks(self):
        leads = (
            self.env["crm.lead"]
            .sudo()
            .search(
                [("callback_datetime", "!=", False), ("callback_datetime", ">=", fields.Datetime.now())],
                order="callback_datetime",
                limit=6,
            )
        )
        return [
            {
                "id": lead.id,
                "name": lead.name,
                "contact": lead.contact_name or lead.partner_name or "",
                "when": fields.Datetime.to_string(fields.Datetime.context_timestamp(self, lead.callback_datetime))[:16],
                "interest": lead.interest_level or "",
            }
            for lead in leads
        ]
