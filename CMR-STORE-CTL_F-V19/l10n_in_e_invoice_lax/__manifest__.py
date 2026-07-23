# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Laxicon Solution (<http://www.laxicon.in>).
#
#    For Module Support : info@laxicon.in
#
##############################################################################
{
    'name' : 'E-Invoice for India with 5 hrs support and 500 E-Invoice Credit',
    'version' : '17.0',
    'summary': ' 5 hr Support and 500 E-Invoice Credit ',
    'sequence': -100,
    'description': """ 5 hr Support and 500 E-Invoice Credit """,
    'author': 'Laxicon Solution',
    'images' : ['static/description/banner.png'],
    'category': 'Invoice',
    'website': 'https://laxicon.in',
    'depends' : ['account', 'l10n_in', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'data/port_code.xml',
        'report/einvoice.xml',
        'views/account_move_view.xml',
        'views/res_compnay.xml',
        'wizard/success_message.xml',
        'wizard/cancel_irn_wiz.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
    'price':95.0,
    'currency':'USD',
    'maintainer': 'Laxicon Solution', 
    'support': 'info@laxicon.in',
}