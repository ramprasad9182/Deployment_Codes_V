{
    'name': 'E-Way Bill Batch and Actions',
    'version': '17.0',
    'summary': 'Batch creation and server actions for E-Way Bill',
    'sequence': -99,
    'description': """Batch creation and server actions for E-Way Bill""",
    'author': 'Laxicon Solution',
    'category': 'Warehouse',
    'website': 'https://laxicon.in',
    'depends': ['lax_ewaybill', 'stock_picking_batch'],
    'data': [
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
