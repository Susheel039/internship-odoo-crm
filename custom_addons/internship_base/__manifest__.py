{
    "name": "Internship Base",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Base models and shared structures for the internship management platform.",
    "author": "Internship CRM",
    "depends": ["base", "mail"],
    "data": [
        "security/internship_security.xml",
        "security/ir.model.access.csv",
        "security/internship_record_rules.xml",
        "views/internship_base_views.xml",
    ],
    "demo": [
        "data/demo_data.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
