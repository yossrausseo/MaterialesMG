from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.journal_id.control_sequence_id and not move.nro_ctrl and move.is_invoice(include_receipts=True):
                move.nro_ctrl = move.journal_id.control_sequence_id.next_by_id()
        return moves