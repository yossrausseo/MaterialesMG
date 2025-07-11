from odoo import models, api
from odoo.exceptions import ValidationError

class Reportnota(models.AbstractModel):
    _name = "report.soltevic_free_form.print_nota"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        self._validate_lines_qty(docs)
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
            'barcode_print': True,
        }
    
    def _validate_lines_qty(self,docs):
        for doc in docs:
            if len(doc.invoice_line_ids.sorted(key=lambda l: (-l.sequence, l.date, l.move_name, -l.id), reverse=True)) > 20:
                raise ValidationError('La factura no puede contener más de 20 productos diferentes, por favor comuniquese con su administrador o sistemas para proceder')