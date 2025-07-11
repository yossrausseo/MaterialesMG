from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    ref_me_currency_id = fields.Many2one('res.currency', related='session_id.ref_me_currency_id',
                                         string="Reference Currency",
                                         store=False)
    session_rate = fields.Float(string="Session Rate", store=True,
                                related='session_id.tax_today',
                                track_visibility='onchange', digits='Dual_Currency_rate')

    amount_tax_ref = fields.Float(string='Ref Taxes', compute='_compute_amount_all_ref')
    amount_total_ref = fields.Float(string='Ref Total', compute='_compute_amount_all_ref')
    amount_paid_ref = fields.Float(string='Ref Paid', compute='_compute_amount_all_ref')
    amount_return_ref = fields.Float(string='Ref Returned', compute='_compute_amount_all_ref')
    margin_ref = fields.Monetary(string="Ref Margin", compute='_compute_margin_ref')
    sum_amount_total_ref = fields.Float(string='Ref Total', compute='_compute_amount_all_ref', store=True)

    @api.depends('session_rate', 'margin')
    def _compute_margin_ref(self):
        for order in self:
            if order.session_rate != 0:
                order.margin_ref = order.margin / order.session_rate

            else:
                order.margin = 0

    @api.depends('amount_tax', 'amount_total', 'session_rate', 'amount_paid')
    def _compute_amount_all_ref(self):
        for order in self:
            if order.session_rate != 0:
                order.amount_paid_ref = order.amount_paid / order.session_rate
                order.amount_return_ref = order.amount_return / order.session_rate
                order.amount_tax_ref = order.amount_tax / order.session_rate
                order.amount_total_ref = order.amount_total / order.session_rate
                order.sum_amount_total_ref = order.amount_total / order.session_rate
            else:
                order.amount_paid_ref = 0
                order.amount_return_ref = 0
                order.amount_tax_ref = 0
                order.amount_total_ref = 0
                order.sum_amount_total_ref = 0
