{
    'name': 'POS Keyboard Shortcut',
    'version': '17.0',
    'description': 'Reducing dependency on mouse clicks and touchscreens.',
    'summary': 'Reducing dependency on mouse clicks and touchscreens.',
    'author': 'Mathys',
    'website': 'https://ahmadyusup.com/pos-keyboard-shortcuts',
    'license': 'OPL-1',
    'category': 'Sales',
    'depends': [
        'base','point_of_sale'
    ],
    'data': [
        'views/index.xml',
    ],
    'images': [
        'static/description/main_screenshot.png',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'ultimate_pos_shortcuts/static/src/app/screens/**/*',
            'ultimate_pos_shortcuts/static/src/app/navbar/**/*',
            'ultimate_pos_shortcuts/static/src/app/category_selector/**/*',
            'ultimate_pos_shortcuts/static/src/app/keyboard_shortcuts/**/*',
            'ultimate_pos_shortcuts/static/src/app/pos_app.js',
            'ultimate_pos_shortcuts/static/src/app/pos_app.xml',
        ],
        'ultimate_pos_shortcuts.hotkeys': [
            ('include', 'point_of_sale._assets_pos'),
            'ultimate_pos_shortcuts/static/src/app/main.js',
        ],
    }
}