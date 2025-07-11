from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    ref_me_currency_id = fields.Many2one('res.currency', related='order_id.ref_me_currency_id',
                                         string="Reference Currency",
                                         store=True)
    session_rate = fields.Float(string="Session Rate", store=True,
                                related='order_id.session_rate',
                                track_visibility='onchange', digits='Dual_Currency_rate')

    price_unit_ref = fields.Float(string='Ref Unit Price', compute='_compute_amount_line_ref', readonly=True,
                                  help='Reference Currency Unit Price')
    total_cost_ref = fields.Float(string='Ref Cost Total', compute='_compute_amount_line_ref', readonly=True,
                                  help='Reference Currency Cost Total')
    margin_ref = fields.Float(string='Ref Margin', compute='_compute_amount_line_ref', readonly=True,
                              help='Reference Currency Margin')
    price_subtotal_ref = fields.Float(string='Ref Subtotal Price', compute='_compute_amount_line_ref', readonly=True,
                                      help='Reference Currency Subtotal Price')
    price_subtotal_incl_ref = fields.Float(string='Ref Incl Subtotal Price', compute='_compute_amount_line_ref',
                                           readonly=True, help='Reference Currency Incl Subtotal Price')

    @api.depends('price_unit', 'total_cost', 'session_rate', 'margin', 'price_subtotal', 'price_subtotal_incl')
    def _compute_amount_line_ref(self):
        for order in self:
            if order.session_rate != 0:
                order.price_unit_ref = order.price_unit / order.session_rate
                order.total_cost_ref = order.total_cost / order.session_rate
                order.margin_ref = order.margin / order.session_rate
                order.price_subtotal_ref = order.price_subtotal / order.session_rate
                order.price_subtotal_incl_ref = order.price_subtotal_incl / order.session_rate
            else:
                order.price_unit_ref = 0
                order.total_cost_ref = 0
                order.margin_ref = 0
                order.price_subtotal_ref = 0
                order.price_subtotal_incl_ref = 0
