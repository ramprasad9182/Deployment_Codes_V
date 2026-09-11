# -*- coding: utf-8 -*-
{
    'name': 'NHCL POS Default Customer',
    'summary': "Set Default Customer in POS",
    'description': 'Set Default Customer in POS',
    'author': 'New Horizons CyberSoft Ltd',
    'company': 'New Horizons CyberSoft Ltd',
    'maintainer': 'New Horizons CyberSoft Ltd',
    'website': "https://www.nhclindia.com",
    'category': 'Point of Sale',
    'version': '17.0.0.1.1',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'nhcl_pos_set_default_customer/static/src/js/get_customer.js',
        ],
    },
    'license': "OPL-1",
    'installable': True,
    'application': True,
    'images': ['static/description/banner.png'],
}
