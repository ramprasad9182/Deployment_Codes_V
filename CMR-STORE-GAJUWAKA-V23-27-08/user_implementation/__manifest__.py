
{
    "name": "License Key Generater for store",
    "depends": [
        "base",'nhcl_customizations','hr','web'
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/user_license_screen_views.xml",
        'views/res_users_views.xml',
        # 'views/login_template_view.xml',
        'data/ir_sequence_data.xml',
        'wizard/license_key_user_wizard_view.xml',
        'data/ir_cron.xml',

    ],
    'license': 'LGPL-3',


}
