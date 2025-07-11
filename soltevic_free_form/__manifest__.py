# -*- coding: utf-8 -*-
{
    "name": "Soltevic free form invoice Avanti ",
    "version": "1.0.0",
    "category": "Accounting/Accounting",
    "application": True,
    "author": "Soltevic2602 C.A",
    "contributors": [
        "Ing. Jonathan Ramirez",
    ],
    "website": "https://venezuela.odoo.com",
    "summary": "Dual currency free form invoice",
    "description": """
        Module to add the free form invoice report based on Avanti format
    """,
    "depends": [
        "base", "account", "account_dual_currency"
    ],
    "data": [
        "report/ir_actions_report.xml",
        "report/free_form.xml",
        "report/nota.xml",
    ],
    "images": [
        "static/description/icon.png"
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
    "cloc_exclude": [
        ".//**/",
    ],
}