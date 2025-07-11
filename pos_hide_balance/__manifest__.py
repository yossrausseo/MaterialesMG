{
    'name': 'Hide Balance in POS',
    'version': '17.0.1.0.0',
    'summary': 'Hide the balance value in POS kanban view',
    'description': 'This module hides the balance value in the kanban view of POS settings',
    'category': 'Point of Sale',
    'author': 'Yosmari Rausseo',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}