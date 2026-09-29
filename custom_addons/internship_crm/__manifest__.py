{
    "name": "Internship CRM",
    "version": "0.1.0",
    "category": "Custom",
    "summary": "CRM and lead management layer for the internship platform.",
    "depends": ["base", "crm", "mail", "calendar", "internship_base"],
    "data": [
        "security/internship_crm_security.xml",
        "security/ir.model.access.csv",
        "views/internship_crm_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
