# -*- coding: utf-8 -*-

from itertools import groupby
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_create_invoice(self):
        """Create the invoice associated to the PO.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        sequence = 10
        for order in self:
            if order.invoice_status != 'to invoice':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()
            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    if pending_section:
                        line_vals = pending_section._prepare_account_move_line()
                        line_vals.update({'sequence': sequence})
                        invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                        sequence += 1
                        pending_section = None
                    line_vals = line._prepare_account_move_line()
                    line_vals.update({'sequence': sequence})
                    invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                    sequence += 1
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(_('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: (x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice',calcular_dual_currency=False)
        for vals in invoice_vals_list:
            vals['tax_today'] = self.env.company.currency_id_dif.inverse_rate
            new_move = AccountMove.with_company(vals['company_id']).create(vals)
            new_move._calculate_amounts_all_usd()  # Asegurar cálculos en USD
            moves |= new_move

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        moves.filtered(lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_move_type()

        return self.action_view_invoice(moves)

class ResCurrency(models.Model):
    _inherit = 'res.currency'
    _name = 'res.currency'  # Forzar la sobreescritura

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True):
        # Asegurar que los parámetros obligatorios estén presentes
        company = company or self.env.company
        date = date or fields.Date.today()
        return super()._convert(from_amount, to_currency, company, date, round)
    
     
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    def _prepare_account_move_line(self, move=False):
        # Asegurar el contexto correcto
        self = self.with_context(
            default_company_id=self.company_id.id,
            default_currency_date=self.order_id.date_order or fields.Date.today()
        )
        vals = super(PurchaseOrderLine, self)._prepare_account_move_line()
        if self.currency_id != self.company_id.currency_id:
            vals['price_unit_usd'] = self.price_unit 
            vals['price_subtotal_usd'] = self.price_subtotal / (self.env.company.currency_id_dif.inverse_rate or 1.0)
        else:
            vals['price_unit_usd'] = self.price_unit / (self.env.company.currency_id_dif.inverse_rate or 1.0)
            vals['price_subtotal_usd'] = self.price_subtotal
        return vals