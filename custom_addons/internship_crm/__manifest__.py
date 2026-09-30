{
    "name": "Internship CRM",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Internship leads on native CRM (crm.lead), conversions and UK contact compliance.",
    "author": "Internship CRM",
    "depends": ["internship_base", "internship_placement", "crm"],
    "data": [
        "security/internship_crm_security.xml",
        "security/ir.model.access.csv",
        "data/crm_data.xml",
        "views/internship_crm_views.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
