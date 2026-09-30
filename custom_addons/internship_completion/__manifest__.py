{
    "name": "Internship Completion",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Final submissions, evaluations, and completion workflow.",
    "author": "Internship CRM",
    "depends": ["base", "mail", "internship_base"],
    "data": [
        "security/internship_completion_security.xml",
        "security/ir.model.access.csv",
        "views/internship_completion_views.xml",
        "report/completion_certificate.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
