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
    'name' : 'E-Invoice for India',
    'version' : '17.2',
    'summary': ' 5 hr support and 500 invoice credit ',
    'sequence': -100,
    'description': """ 5 hr support and 500 invoice credit """,
    'author': 'Laxicon Solution',
    'images' : ['static/description/icon.png'],
    'category': 'Invoice',
    'website': 'https://laxicon.in',
    'depends' : ['account', 'l10n_in', 'base'],
    'data': [
        'security/ir.model.access.csv',
        # 'data/uqc_code.xml',
        # 'data/port_code.xml',
        'report/einvoice.xml',
        'views/account_move_view.xml',
        'views/res_compnay.xml',
        # 'views/uom_uom.xml',
        'wizard/success_message.xml',
        'wizard/cancel_irn_wiz.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
    'price':49.0,
    'currency':'USD',
    'maintainer': 'Laxicon Solution', 
    'support': 'info@laxicon.in',
}