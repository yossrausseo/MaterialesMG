# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    pos_amount_authorized_diff_ref = fields.Float(related='pos_config_id.amount_authorized_diff_ref', readonly=False)
