from odoo import fields, models, api, _
from odoo.tools import formatLang, float_is_zero
from odoo.exceptions import ValidationError

class PosPayment(models.Model):
    _inherit = "pos.payment"

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Ref.",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'VES')],
                                                                                           limit=1), )

    tax_today = fields.Float(string="Tasa Sesión", store=True, related='session_id.tax_today',
                             tracking=True, digits='Dual_Currency_rate')

    amount_ref = fields.Monetary(currency_field='currency_id_dif', string='Monto Ref', store=True, readonly=True, compute='_compute_amount_ref', digits='Dual_Currency')

    @api.depends('amount', 'tax_today')
    def _compute_amount_ref(self):
        for payment in self:
            payment.amount_ref = payment.amount / (payment.tax_today if payment.tax_today > 0 else 1)

    def name_get(self):
        res = []
        for payment in self:
            if payment.name:
                res.append((payment.id, '%s %s - %s' % (payment.name, formatLang(self.env, payment.amount, currency_obj=payment.currency_id), formatLang(self.env, payment.amount_ref, currency_obj=payment.currency_id_dif))))
            else:
                res.append((payment.id, '%s - %s' % (formatLang(self.env, payment.amount, currency_obj=payment.currency_id), formatLang(self.env, payment.amount_ref, currency_obj=payment.currency_id_dif))))
        return res

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(PosPayment, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                           orderby=orderby, lazy=lazy)
        res = super(PosPayment, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res