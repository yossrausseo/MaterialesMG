# -*- coding: utf-8 -*-
{
    'name': 'Venezuela: POS IGTF',
    'version': '17.0.1.2.0',
    'author': 'Joinners Méndez',
    'company': 'Soltevic 2602',
    'maintainer': 'Soltevic 2602',
    'website': 'https://soltevic.com',
    'category': 'Sales/Point of Sale',
    'summary': 'IGTF en el POS',
    # 'depends': ['point_of_sale','l10n_ve_pos_dual_currency'],
    'depends': ['point_of_sale', 'pos_show_dual_currency'],
    'data': [
        'views/inherited_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_igtf_tax/static/src/scss/**/*',
            'pos_igtf_tax/static/src/xml/**/*',
            'pos_igtf_tax/static/src/js/**/*',
        ],
    },
    'license': 'LGPL-3',
}
