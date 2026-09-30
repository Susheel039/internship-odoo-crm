{
    "name": "Call Tracking",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Call tracking and voice workflow integration for the internship CRM.",
    "author": "Internship CRM",
    "depends": ["base", "crm", "mail", "calendar", "internship_base"],
    "data": [
        "security/internship_vapi_security.xml",
        "security/ir.model.access.csv",
        "views/internship_vapi_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
