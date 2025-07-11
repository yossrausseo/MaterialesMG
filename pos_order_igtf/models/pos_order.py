from odoo import api, fields, models, _

class PosOrder(models.Model):
    _inherit = "pos.order"

    currency_id_dif = fields.Many2one('res.currency', string='Moneda $', default=lambda self: self.env.company.currency_id_dif)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    total_igtf = fields.Monetary(currency_field='company_currency_id', compute="_compute_igtf_data")
    tax_base_igtf = fields.Monetary(currency_field='company_currency_id', compute="_compute_igtf_data")
    total_amount = fields.Monetary(currency_field='company_currency_id', compute="_compute_igtf_data")
    total_amount_igtf = fields.Monetary(currency_field='company_currency_id', compute="_compute_igtf_data")
    total_igtf_usd = fields.Monetary(currency_field='currency_id_dif', compute="_compute_igtf_data")
    tax_base_igtf_usd = fields.Monetary(currency_field='currency_id_dif', compute="_compute_igtf_data")
    total_amount_usd = fields.Monetary(currency_field='currency_id_dif', compute="_compute_igtf_data")
    total_amount_igtf_usd = fields.Monetary(currency_field='currency_id_dif', compute="_compute_igtf_data")

    igtf_payment_lines = fields.One2many(
        'pos.order.igtf.payment.line',
        'order_id',
        string='Pagos con IGTF',
        compute='_compute_igtf_data',
        readonly=False  # ¡CRUCIAL! Permite la creación de registros
    )
    
    igtf_payment_methods = fields.Char(
        string='Resumen Métodos IGTF',
        compute='_compute_igtf_data',
        store=True
    )

    @api.depends('payment_ids', 'payment_ids.payment_method_id')
    def _compute_igtf_data(self):
        for order in self:
            # 1. Calculamos el subtotal REAL excluyendo la línea de IGTF
            subtotal_sin_igtf = sum(
                line.price_subtotal_incl for line in order.lines 
                if 'IGTF' not in line.product_id.name   # Excluimos la línea de IGTF si existe
            )

            # 2. Procesamos pagos en orden
            lines_to_create = []
            remaining_amount = subtotal_sin_igtf
            print('remaining_amount:', remaining_amount)
            total_igtf_calculado = 0
            tax_base_igtf = 0
            payment_info = []

            for payment in order.payment_ids.sorted(key=lambda p: p.id):
                pm = payment.payment_method_id
                amount = payment.amount

                if remaining_amount <= 0:
                    break

                if pm.x_igtf_percentage > 0 and pm.x_is_foreign_exchange:
                    applicable_amount = min(amount, remaining_amount)
                    igtf_amount = applicable_amount * pm.x_igtf_percentage / 100
                    
                    tax_base_igtf += applicable_amount
                    total_igtf_calculado += igtf_amount

                    lines_to_create.append({
                        'order_id': order.id,
                        'payment_method_id': pm.id,
                        'base_amount': applicable_amount,
                        'base_amount_usd': applicable_amount / (order.session_rate or 1.0),
                        'igtf_percentage': pm.x_igtf_percentage,
                        'igtf_amount': igtf_amount,
                        'igtf_amount_usd': igtf_amount / (order.session_rate or 1.0),
                    })
                    payment_info.append(f"{pm.name}: {applicable_amount}")

                remaining_amount -= amount

            # 3. Obtenemos el IGTF que ya está en las líneas del pedido
            igtf_en_lineas = sum(
                line.price_subtotal for line in order.lines
                if 'IGTF' in line.product_id.name
            )

            # 4. Verificamos coherencia entre lo calculado y lo existente
            if abs(total_igtf_calculado - igtf_en_lineas) > 0.01:
                print(f"Discrepancia en IGTF: Calculado={total_igtf_calculado}, En líneas={igtf_en_lineas}")

            # 5. Actualizamos registros
            order.igtf_payment_lines.unlink()
            if lines_to_create:
                self.env['pos.order.igtf.payment.line'].create(lines_to_create)

            # 6. Calculamos totales usando el IGTF que ya está en líneas
            order.update({
                'tax_base_igtf': tax_base_igtf,
                'total_igtf': igtf_en_lineas,  # Usamos el valor que ya está en líneas
                'total_amount': subtotal_sin_igtf,
                'total_amount_igtf': subtotal_sin_igtf + igtf_en_lineas,
                'tax_base_igtf_usd': round(tax_base_igtf / (order.session_rate or 1.0), 2),
                'total_igtf_usd': round(igtf_en_lineas / (order.session_rate or 1.0), 2),
                'total_amount_usd': round((subtotal_sin_igtf) / (order.session_rate or 1.0), 2),
                'total_amount_igtf_usd': round((subtotal_sin_igtf + igtf_en_lineas) / (order.session_rate or 1.0), 2),
                'igtf_payment_methods': '; '.join(payment_info) if payment_info else 'N/A'
            })

class PosOrderIgtfPaymentLine(models.Model):
    _name = 'pos.order.igtf.payment.line'
    _description = 'Líneas de pago con IGTF'
    _order = 'id desc'

    order_id = fields.Many2one('pos.order', string='Orden POS', required=True, ondelete='cascade')
    payment_method_id = fields.Many2one('pos.payment.method', string='Método de Pago', required=True)
    base_amount = fields.Monetary(string='Base Imponible', currency_field='currency_id')
    base_amount_usd = fields.Monetary(string='Base Imponible $', currency_field='currency_id')
    igtf_percentage = fields.Float(string='% IGTF', digits=(12, 2))
    igtf_amount = fields.Monetary(string='Monto IGTF', currency_field='currency_id')
    igtf_amount_usd = fields.Monetary(string='Monto IGTF $', currency_field='currency_id')
    
    currency_id = fields.Many2one(
        'res.currency',
        related='order_id.company_id.currency_id',
        string='Moneda',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='order_id.company_id.currency_id',
        string='Moneda',
        store=True
    )