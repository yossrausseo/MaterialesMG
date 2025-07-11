# from odoo import fields, models, api, _
# from odoo.tools import formatLang, float_is_zero
# from odoo.exceptions import ValidationError

# class ResCompany(models.Model):
#     _inherit = "res.company"

#     currency_id_dif = fields.Many2one("res.currency",
#                                       string="Moneda Ref.",
#                                       default=lambda self: self.env['res.currency'].search([('name', '=', 'VEF')],
#                                                                                            limit=1), )