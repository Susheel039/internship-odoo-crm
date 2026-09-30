{
    "name": "Internship Reporting",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Phase 6 reporting and KPI dashboard for the internship platform.",
    "author": "Internship CRM",
    "depends": [
        "base",
        "mail",
        "internship_base",
        "internship_monitoring",
        "internship_completion",
        "internship_crm",
        "internship_vapi",
    ],
    "data": [
        "security/internship_reporting_security.xml",
        "security/ir.model.access.csv",
        "views/internship_reporting_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
