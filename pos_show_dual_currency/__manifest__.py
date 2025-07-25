
{
    "name": """Venezuela: POS show dual currency""",
    "summary": """Adds price  of other currency at products in POS""",
    "category": "Point Of Sale",
    "version": "17.0.1.2.0",
    "application": False,
    'author': 'Joinners Méndez',
    'company': 'Soltevic 2602 C.A.',
    'maintainer': 'Joinners Méndez',
    'website': 'https://soltevic.com',
    "depends": ["point_of_sale","pos_sale","stock", 'account',],
    "data": [
        "views/pos_payment_method.xml",
        "views/pos_session.xml",
        "views/pos_payment.xml",
        "views/pos_config.xml",
        "views/res_config_settings.xml",
        'views/pos_order.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'pos_show_dual_currency/static/src/css/pos.css',
            'pos_show_dual_currency/static/src/**/*',
        ],
    },
    "license": "OPL-1",
    'images': [
        'static/description/thumbnail.png',
    ],
    "price": 500,
    "currency": "USD",
    "auto_install": False,
    "installable": True,
}
