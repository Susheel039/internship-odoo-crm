{
    "name": "Internship Base",
    "version": "0.1.0",
    "category": "Custom",
    "summary": "Base models and shared structures for the internship management platform.",
    "author": "Internship CRM",
    "depends": ["base", "mail"],
    "data": [
        "security/internship_security.xml",
        "security/ir.model.access.csv",
        "security/internship_record_rules.xml",
        "views/internship_base_views.xml",
        "data/demo_data.xml",
    ],
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
