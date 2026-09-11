# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'NHCL Walkin Report',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Walkin report and Slot Master management for POS',
    'author': 'New Horizons CyberSoft Ltd',
    'company': 'New Horizons CyberSoft Ltd',
    'maintainer': 'New Horizons CyberSoft Ltd',
    'website': "https://www.nhclindia.com",
    'license': 'AGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/year_master_views.xml',
        'views/walkin_screen_views.xml',
        'views/walkin_sequence.xml',
        'views/day_reporting_views.xml',
        'views/hour_reporting_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
