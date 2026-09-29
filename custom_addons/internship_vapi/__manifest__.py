{
    "name": "Call Tracking",
    "version": "0.1.0",
    "category": "Custom",
    "summary": "Call tracking and voice workflow integration for the internship CRM.",
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
