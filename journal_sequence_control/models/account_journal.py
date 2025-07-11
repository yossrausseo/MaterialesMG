from odoo import models, fields, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    control_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Secuencia de Número de Control',
        help="Secuencia para generar el número de control en facturas de este diario"
    )
    next_control_seq = fields.Integer(string="Próximo número", related="control_sequence_id.number_next_actual", readonly=True)
    
    def _create_control_sequence(self):
        """Crea una secuencia para el número de control del diario"""
        self.ensure_one()  # Asegura que solo se trabaja con un registro
        if not self.control_sequence_id:
            seq_vals = {
                'name': f'Nro. Control Facturas - {self.name}',
                'code': f'account.journal.{self.id}.control',
                'prefix': f'CTRL-{self.code}/',
                'padding': 8,
                'company_id': self.company_id.id,
            }
            self.control_sequence_id = self.env['ir.sequence'].create(seq_vals)
    
    @api.model
    def create(self, vals):
        journal = super().create(vals)
        journal._create_control_sequence()
        return journal
    
    @api.model
    def init_sequences_for_existing_journals(self):
        """Método específico para inicialización desde XML"""
        journals = self.search([('type', 'in', ['sale'])])
        for journal in journals:
            journal._create_control_sequence()
        return True