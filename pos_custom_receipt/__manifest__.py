{
    'name': 'Imprimir factura personalizada en el POS',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Usa plantilla personalizada para facturas del POS',
    'description': """
        Reemplaza la factura nativa del POS por una plantilla personalizada
    """,
    'depends': ['point_of_sale', 'account', 'soltevic_free_form'],
    'data': [
        'views/pos_invoice.xml',
    ],
    'assets': {
        #'point_of_sale.assets': [
        #    'pos_custom_receipt/static/src/js/pos_custom_receipt.js',
        #],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}