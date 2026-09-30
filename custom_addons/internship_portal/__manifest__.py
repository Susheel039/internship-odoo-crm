{
    "name": "Internship Portal",
    "version": "19.0.1.0.0",
    "category": "Custom",
    "summary": "Portal pages for students and line managers: placement, documents, monthly records, leave, "
    "agreement, final report, evaluation, certificate and feedback.",
    "author": "Internship CRM",
    "depends": ["internship_agreement", "internship_monitoring", "internship_completion", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/internship_portal_rules.xml",
        "views/portal_templates.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
