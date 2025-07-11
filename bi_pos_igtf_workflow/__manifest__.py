# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'POS IGTF Workflow for Venezuela',
    'version': '17.0.0.0',
    'category': 'Point of Sale',
    'summary': 'POS IGTF payment charges POS Impuesto de Grandes Transacciones Financieras point of sale IGTF workflow pos IGTF workflow POS IGTF charges POS IGTF Venezuela pos Venezuela IGTF Accounting pos Venezuela Accounting POS IGTF Accounting pos IGTF payment method',
    'description' :"""
        POS IGTF (Impuesto de Grandes Transacciones Financieras) Odoo app help businesses comply with this tax requirement on large financial transactions in Venezuela. This app is designed to streamline the process of calculating and paying IGTF taxes, also allows businesses to set their own IGTF tax rates based on their specific needs and automatically calculates the IGTF tax for each transaction based on the amount of the transaction and the applicable tax rate.
    """,
    'author': 'BrowseInfo',
    'website': "https://www.browseinfo.com/demo-request?app=bi_pos_igtf_workflow&version=17&edition=Community",
    "price": 99,
    "currency": 'EUR',
    'depends': ['base','point_of_sale'],
    'data': [
        'data/igtf_product.xml',
        'report/pos_report.xml',
        'views/pos_view.xml',
    ],
    'assets':{
        'point_of_sale._assets_pos': [
            '/bi_pos_igtf_workflow/static/src/app/models.js',
            '/bi_pos_igtf_workflow/static/src/app/orderreceipt.js',
            '/bi_pos_igtf_workflow/static/src/app/orderreceipt.xml',
            '/bi_pos_igtf_workflow/static/src/app/paymentscreen.js',
            '/bi_pos_igtf_workflow/static/src/app/paymentscreenstatus.js',
            '/bi_pos_igtf_workflow/static/src/app/paymentscreenstatus.xml',
            '/bi_pos_igtf_workflow/static/src/app/posdb.js',
            '/bi_pos_igtf_workflow/static/src/app/pos_store.js',
           
         ],
    },
    'demo': [],
    'license':'OPL-1',
    'test': [],
    'installable': True,
    'auto_install': False,
    'live_test_url':"https://www.browseinfo.com/demo-request?app=bi_pos_igtf_workflow&version=17&edition=Community",
    "images":['static/description/Banner.gif'],
}
