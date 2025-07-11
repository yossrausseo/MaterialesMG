{
    'name': 'POS Validation Payment Method',
    'version': '17.0.1.0',
    'summary': 'Add a validation message at the POS before confirming the order',
    'description': 'This module validates that a payment method has been selected for the changes before confirming the order at the point of sale.',
    'author': 'Yosmari Rausseo',
    'category': 'Point of Sale',
    'depends': ['point_of_sale'],
    'data': [
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_validation_payment_method/static/src/**/*',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}