{
    'name': 'POS Invoice Customization',
    'version': '17.0.1.0',
    'summary': 'Customize POS invoice template',
    'description': 'Module to customize the point of sale invoice template',
    'author': 'Yosmari Rausseo',
    'category': 'Point of Sale',
    'depends': ['point_of_sale', 'account','soltevic_free_form'],
    'data': [
        'views/pos_invoice_templates.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_invoice_custom/static/src/xml/pos_invoice_template.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}