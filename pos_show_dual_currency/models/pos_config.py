from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang
from datetime import datetime
from uuid import uuid4
import pytz


class PosConfig(models.Model):
    _inherit = 'pos.config'

    last_session_closing_cash_me_ref = fields.Float(compute='_compute_last_session_me_ref')
    amount_authorized_diff_ref = fields.Float('Diferencia autorizada $')

    @api.depends('session_ids')
    def _compute_last_session_me_ref(self):
        PosSession = self.env['pos.session']
        for pos_config in self:
            session = PosSession.search_read(
                [('config_id', '=', pos_config.id), ('state', '=', 'closed')],
                ['cash_register_balance_end_real_mn_ref'],
                order="stop_at desc", limit=1)
            if session:
                pos_config.last_session_closing_cash_me_ref = session[0]['cash_register_balance_end_real_mn_ref']
            else:
                pos_config.last_session_closing_cash_me_ref = 0
