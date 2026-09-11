# -*- coding: utf-8 -*-
{
    "name": "Tracking Modules",
    "version": "1.0",
    "sequence": 2,
    "author": "NHCL",
    "maintainer": "NHCL",
    "depends": ['base'],
    "external_dependencies": {"python": ["bs4"]},
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/module_audit_log_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    "auto_install": False,
}
