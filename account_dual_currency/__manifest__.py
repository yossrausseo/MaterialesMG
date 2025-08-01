# -*- coding: utf-8 -*-
{
    'name': "Venezuela: Account Dual Currency",
    'category': 'Account',
    'license': 'Other proprietary',
    'summary': """Esta aplicación permite manejar dualidad de moneda en Contabilidad.""",
    'author': 'José Luis Vizcaya López',
    'company': 'José Luis Vizcaya López',
    'maintainer': 'José Luis Vizcaya López',
    'website': 'https://github.com/birkot',
    'description': """
    
        - Mantener como moneda principal Bs y $ como secundaria.
        - Facturas en Bs pero manteniendo deuda en $.
        - Tasa individual para cada Factura de Cliente y Proveedor.
        - Tasa individual para Asientos contables.
        - Visualización de Débito y Crédito en ambas monedas en los apuntes contables.
        - Conciliación total o parcial de $ y Bs en facturas.
        - Registro de pagos en facturas con tasa diferente a la factura.
        - Registro de anticipos en el módulo de Pagos de Odoo, manteniendo saldo a favor en $ y Bs.
        - Informe de seguimiento en $ y Bs a la tasa actual.
        - Reportes contables en $ (Vencidas por Pagar, Vencidas por Cobrar y Libro mayor de empresas)
        - Valoración de inventario en $ y Bs a la tasa actual

    """,
    'depends': [
                'base','l10n_ve_full','account','account_reports','account_followup','web',
                'stock_account','account_accountant','analytic','stock_landed_costs','account_debit_note','mail',
                'account_reports_cash_basis', 'account_asset','product','crm','crm_enterprise'
                ],
    'data':[
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'views/res_currency.xml',
        'views/res_config_settings.xml',
        'views/account_move_view.xml',
        'views/account_move_line.xml',
        #'views/search_template_view.xml',
        'wizard/account_payment_register.xml',
        'views/account_payment.xml',
        'views/product_template.xml',
        'views/product_product_views.xml',
        'views/stock_landed_cost.xml',
        'views/stock_valuation_layer.xml',
        'views/account_journal_dashboard.xml',
        'data/decimal_precision.xml',
        'data/cron.xml',
        'data/channel.xml',
        'views/effective_date_change.xml',
        'views/product_template_attribute_value.xml',
        'views/account_asset.xml',
        'views/view_bank_statement_line_tree_bank_rec_widget.xml',
        'wizard/generar_retencion_igtf_wizard.xml',
        'views/res_partner.xml',
    ],
    'assets': {
        'web.assets_backend': [
            #'account_dual_currency/static/src/components/filter_date.xml',
            'account_dual_currency/static/src/components/filter.xml',
            #'account_dual_currency/static/src/components/account_payment.xml',
            #'account_dual_currency/static/src/components/filters.js',
            'account_dual_currency/static/src/js/**/*',
            'account_dual_currency/static/src/xml/**/*',
        ],
        'web.assets_qweb': [
            'account_dual_currency/static/src/components/filter.xml',
        ],
    },
    'images': [
        'static/description/thumbnail.png',
    ],
    'live_test_url': 'https://demo16-venezuela.odoo.com/web/login',
    "price": 3000,
    "currency": "USD",
    'installable' : True,
    'application' : False,
}

