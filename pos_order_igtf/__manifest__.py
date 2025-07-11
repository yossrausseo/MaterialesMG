{
    'name': 'POS Order IGTF',
    'version': '17.0.1.0',
    'summary': 'Add tab for IGTF information in POS sales order',
    'description': 'This module adds a new tab for IGTF information in the POS sales order',
    'author': 'Yosmari Rausseo',
    'category': 'Point of Sale',
    'depends': ['point_of_sale', 'pos_igtf_tax', 'pos_show_dual_currency'],
    'data': [
        'views/pos_order.xml',
        'security/ir.model.access.csv'
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}