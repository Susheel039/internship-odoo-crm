{
    "name": "Internship Monitoring",
    "version": "19.0.2.0.0",
    "category": "Custom",
    "summary": "Monitoring, attendance, meetings, and performance management for internships.",
    "author": "Internship CRM",
    "depends": ["base", "mail", "calendar", "internship_base"],
    "data": [
        "security/internship_monitoring_security.xml",
        "security/ir.model.access.csv",
        "views/internship_monitoring_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
