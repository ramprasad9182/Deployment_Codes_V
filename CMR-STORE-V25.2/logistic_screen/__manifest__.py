{
    'name': 'Logistic Screen',
    'version': '1.0',
    'category': 'Logistics',
    "author": "New Horizons Cybersoft Ltd",
    "website": "https://www.nhclindia.com/",
    'summary': 'Logistics',
    'description': """
This module contains all the common features of Transport and Check.
    """,
    'depends': ['purchase', 'base','nhcl_customizations','transport_dashboard'],

    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/logistic_screen_entry.xml',
        'views/transports_check_view.xml',
        'views/delivery_check_view.xml',
        'views/open_parel.xml',
    ],
    'assets': {
            'web.assets_backend': [
                'logistic_screen/static/src/js/logistic_dashboard.js',
                'logistic_screen/static/src/xml/logistic_dashboard.xml',
                'logistic_screen/static/src/css/logistic_dashboard.css',
            ],
        },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
