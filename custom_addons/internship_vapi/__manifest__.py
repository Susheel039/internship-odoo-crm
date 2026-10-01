{
    "name": "Internship Voice AI (Vapi)",
    "version": "19.0.2.3.0",
    "category": "Custom",
    "summary": "Outbound and inbound AI calls with Vapi: call queue, webhook, tools, lead creation.",
    "author": "Internship CRM",
    "depends": ["internship_crm", "internship_placement", "internship_monitoring"],
    "external_dependencies": {"python": ["requests", "phonenumbers"]},
    "data": [
        "security/internship_vapi_security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/internship_vapi_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
