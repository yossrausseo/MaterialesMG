{
    'name': 'POS Always Invoice',
    'version': '17.0.1.0',
    'summary': 'Sets invoice option to true by default in POS',
    'category': 'Point of Sale',
    'author': 'Yosmari Rausseo',
    'depends': ["point_of_sale","pos_sale"],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_always_invoice/static/src/**/*',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}