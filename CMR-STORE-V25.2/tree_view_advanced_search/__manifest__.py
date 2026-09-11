
{
    'name': 'Tree view Advanced Search',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': """Advanced search feature in all tree views""",
    'description': """It enhances user experience by enabling both single and 
    multiple search capabilities across all tree view displays. It facilitates 
    multiple search filters on single columns, allowing users to easily search 
    through various data types such as text, date/datetime, many2one, integer, 
    and float columns.""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['web', 'purchase', 'account'],
    'assets': {
        'web.assets_backend': [
            'tree_view_advanced_search/static/src/js/components/date_range.js',
            'tree_view_advanced_search/static/src/js/components/date_range.xml',
            'tree_view_advanced_search/static/src/js/components/many2one_search.js',
            'tree_view_advanced_search/static/src/js/components/many2one_search.xml',
            'tree_view_advanced_search/static/src/css/search_bar_view.css',
            'tree_view_advanced_search/static/src/js/list_renderer_search_bar.js',
            'tree_view_advanced_search/static/src/xml/list_renderer_search_bar.xml',
            'tree_view_advanced_search/static/src/js/list_controller.js',
            'tree_view_advanced_search/static/src/xml/list_controller.xml',
            'tree_view_advanced_search/static/src/js/db_delete_lock.js',

        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
