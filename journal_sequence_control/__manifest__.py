{
    'name': 'Control sequence for invoices',
    'version': '17.0.1.0.0',
    'summary': 'Allows you to configure sequences for the control number in invoices',
    'description': """
        This module allows you to configure a sequence per ledger to automatically assign the control number on invoices.
    """,
    'author': 'Yosmari Rausseo',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_journal_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}