{
    'name': "POS Receipt Sequence",
    'version': '17.0.0.0',
    'depends': ['base', 'point_of_sale'],
    'data': [
        'views/res_config_settings.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_receipt_sequence/static/src/app/db.js',
            'pos_receipt_sequence/static/src/app/pos_store.js',
            'pos_receipt_sequence/static/src/app/receipt/models.js',
            'pos_receipt_sequence/static/src/app/receipt/orderreceipt.js',
            'pos_receipt_sequence/static/src/app/receipt/paymentscreen.js',
            'pos_receipt_sequence/static/src/app/receipt/save_button.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}

