# -*- coding: utf-8 -*-
{
    "name" : "NHCL Product Multiple Barcodes",
    "version" : "17.0.0.0",
    "category" : "Warehouse",
    'author': 'New Horizons CyberSoft Ltd',
    'company': 'New Horizons CyberSoft Ltd',
    'maintainer': 'New Horizons CyberSoft Ltd',
    'website': "https://www.nhclindia.com",
    'summary': 'Product Multi Barcode for Product multiple barcode for product barcode search product based on barcode product barcode generator product different barcode product many barcode product multi barcode for sale multi barcode create multiple barcode for product',
    "description": """
    
        Multi barcode for product in odoo,
        Assigned multiple barcode to single product in odoo,
        Search product based on multiple barcode in odoo,
        Raised warning when assigned same barcode to product in odoo,
        Multiple barcode for sale order or purchase order in odoo,
        Multiple barcode for invoice or vendor bill in odoo,
        Multiple barcode for delivery and shipment in odoo,

    """,
    "depends" : ['base','sale_management','purchase','account','stock','nhcl_customizations','point_of_sale'],
    "data": [
        'security/ir.model.access.csv',
        'views/res_config_inherit.xml',
        'views/product.xml',
        'views/inherit_view.xml',
        'wizard/sr_import_multi_barcode.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            "nhcl_pos_bi_multi_barcode_for_product/static/src/app/product/pos_store.js",
            "nhcl_pos_bi_multi_barcode_for_product/static/src/app/product/productscreen.js",
            "nhcl_pos_bi_multi_barcode_for_product/static/src/app/product/posdb.js",
        ],

    },
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://youtu.be/6pCMrTdyp_Q',
    "images":["static/description/Banner.gif"],
    'license': 'OPL-1',
}
