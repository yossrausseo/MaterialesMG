# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta
from functools import partial
from itertools import groupby
from collections import defaultdict

import psycopg2
import pytz
import re

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero, float_round, float_repr, float_compare
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND
import base64

_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
	_inherit = 'pos.config'


	igtf_journal_id = fields.Many2one('account.journal', 'Partial Payment Journal',domain="[('is_igtf', '=', True)]")
	igtf_tax = fields.Float(
		string='IGTF Tax%', default=2.00)

class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	igtf_journal_id = fields.Many2one(related='pos_config_id.igtf_journal_id', readonly=False)
	igtf_tax = fields.Float(related='pos_config_id.igtf_tax', readonly=False)

	@api.model_create_multi
	def create(self, vals_list):
		res=super(ResConfigSettings, self).create(vals_list)
		for vals in vals_list:
			igtf_tax =vals.get('igtf_tax')
			if igtf_tax:
					if (igtf_tax < 0.2 or igtf_tax > 20):
						raise ValidationError(_('IGTF Tax should in between 0.2% to 20%'))
		return res


	def write(self, vals):
		res=super(ResConfigSettings, self).write(vals)
		if self.igtf_tax:
			if (self.igtf_tax < 0.2 or self.igtf_tax > 20):
				raise ValidationError(_('IGTF Tax should in between 0.2% to 20%'))
		return res
	
class account_journal(models.Model):
	_inherit = 'account.journal'

	is_igtf = fields.Boolean(string='Is IGTF')


class pos_payment_method(models.Model):
	_inherit = 'pos.payment.method'
	

	is_igtf = fields.Boolean(string='Is IGTF', related='journal_id.is_igtf', readonly=False)


	# @api.constrains('is_igtf')
	# def validate_single_api_key(self):
	# 	records = self.search([])
	# 	count = 0
	# 	for record in records:
	# 		if record.is_igtf == True:
	# 			count += 1
	# 	if(count >1):
	# 		raise ValidationError("You can not make multiple IGTF payment method")

class pos_order(models.Model):
	_inherit = 'pos.order'


	def _default_journal_id(self):
		return self.env['account.journal'].search([('company_id', '=', self.env.company.id), ('is_igtf', '=', True)], limit=1)

	igtf_order_tax = fields.Float(
		string='% IGTF Tax',readonly=True
	)
	payment_method_id = fields.Many2one(
		'pos.payment.method',
		string='IGTF Payment Method',readonly=True
	)
	igtf_amount = fields.Float(
		string='IGTF Amount',readonly=True
	)
	total_amount_with_igtf = fields.Float(
		string='Total Amount + IGTF',readonly=True
	)
	igtf_journal_id = fields.Many2one(
		'account.journal',
		string='IGTF Journal',readonly=True ,default=_default_journal_id
	)

	@api.model
	def _order_fields(self, ui_order):
		res = super(pos_order, self)._order_fields(ui_order)
		res['igtf_amount'] = ui_order.get('igtf_amount',0.0)
		return res


	def _export_for_ui(self, order):
		result = super(pos_order, self)._export_for_ui(order)
		result['igtf_amount'] = order.igtf_amount
		return result


	@api.onchange('payment_ids', 'lines')
	def _onchange_amount_all(self):
		for order in self:
			if not order.pricelist_id.currency_id:
				raise UserError(_("You can't: create a pos order from the backend interface, or unset the pricelist, or create a pos.order in a python test with Form tool, or edit the form view in studio if no PoS order exist"))
			currency = order.pricelist_id.currency_id
			order.amount_paid = sum(payment.amount for payment in order.payment_ids)
			order.amount_return = sum(payment.amount < 0 and payment.amount or 0 for payment in order.payment_ids)
			order.amount_tax = currency.round(sum(self._amount_line_tax(line, order.fiscal_position_id) for line in order.lines))
			amount_untaxed = currency.round(sum(line.price_subtotal for line in order.lines))
			order.amount_total = order.amount_tax + amount_untaxed + order.igtf_amount


	# @api.model
	# def _process_order(self, order, draft, existing_order):
	#   """Create or update an pos.order from a given dictionary.

	#   :param dict order: dictionary representing the order.
	#   :param bool draft: Indicate that the pos_order is not validated yet.
	#   :param existing_order: order to be updated or False.
	#   :type existing_order: pos.order.
	#   :returns: id of created/updated pos.order
	#   :rtype: int
	#   """
	#   order = order['data']
	#   pos_session = self.env['pos.session'].browse(order['pos_session_id'])
	#   if pos_session.state == 'closing_control' or pos_session.state == 'closed':
	#       order['pos_session_id'] = self._get_valid_session(order).id

	#   pos_order = False
	#   if not existing_order:
	#       pos_order = self.create(self._order_fields(order))
	#   else:
	#       pos_order = existing_order
	#       pos_order.lines.unlink()
	#       order['user_id'] = pos_order.user_id.id
	#       pos_order.write(self._order_fields(order))
	#   payment_method_id=self.env['pos.payment.method'].search([('is_igtf','=',True)])
	#   if pos_order.igtf_amount:
	#       pos_order.write({'igtf_order_tax':pos_order.config_id.igtf_tax,
	#                         'payment_method_id':payment_method_id.id,
	#                         'total_amount_with_igtf':pos_order.amount_total,
	#                         'igtf_journal_id':pos_order.config_id.igtf_journal_id,
	#                       })
	#   pos_order = pos_order.with_company(pos_order.company_id)
	#   self = self.with_company(pos_order.company_id)
	#   self._process_payment_lines(order, pos_order, pos_session, draft)

	#   if not draft:
	#       try:
	#           pos_order.action_pos_order_paid()
	#       except psycopg2.DatabaseError:
	#           # do not hide transactional errors, the order(s) won't be saved!
	#           raise
	#       except Exception as e:
	#           _logger.error('Could not fully process the POS Order: %s', tools.ustr(e))
	#       pos_order._create_order_picking()
	#       pos_order._compute_total_cost_in_real_time()

	#   if pos_order.to_invoice and pos_order.state == 'paid':
	#       pos_order._generate_pos_order_invoice()

	#   return pos_order.id
	@api.model
	def _process_order(self, order, draft, existing_order):
		new = super(pos_order,self)._process_order(order, draft, existing_order)
		Pos_Order = self.browse(new)
		order = order['data']
		pos_session = self.env['pos.session'].browse(order['pos_session_id'])
		pos_config = pos_session.config_id
		payment_method_id=self.env['pos.payment.method'].search([('is_igtf','=',True)])
		print(payment_method_id)
		# print(payment_method_id.id)
		# print(payment_method_id.name)
		if Pos_Order.igtf_amount:
			Pos_Order.write({'igtf_order_tax':pos_config.igtf_tax,
							  'payment_method_id':payment_method_id.id,
							  'total_amount_with_igtf':Pos_Order.amount_total,
							  'igtf_journal_id':pos_config.igtf_journal_id,
							})
		return new

	def _prepare_invoice_lines(self):
		res= super(pos_order, self)._prepare_invoice_lines()
		prod = self.env['product.product'].search([('default_code','=','bi_igtf')])
		if self.igtf_amount:
			res.append((0, None, {
				'product_id': prod.id,
				'quantity': 1,
				'price_unit': float(self.igtf_amount),
				'tax_ids': [(6, 0, [])],
				'is_igtf_line': True,
			}))

		return res

	def _generate_pos_order_invoice(self):
		moves = self.env['account.move']

		for order in self:
			# Force company for all SUPERUSER_ID action
			if order.account_move:
				moves += order.account_move
				continue

			if not order.partner_id:
				raise UserError(_('Please provide a partner for the sale.'))

			move_vals = order._prepare_invoice_vals()
			new_move = order._create_invoice(move_vals)
			if order.igtf_amount:
				new_move.update({
					'is_igtf_invoice':True,
					'invoice_igtf_amount':order.igtf_amount,
				})
			order.write({'account_move': new_move.id, 'state': 'invoiced'})
			new_move.sudo().with_company(order.company_id).with_context(skip_invoice_sync=True)._post()
			moves += new_move
			payment_moves = order._apply_invoice_payments()
			if self.env.context.get('generate_pdf', True):
				template = self.env.ref(new_move._get_mail_template())
				new_move.with_context(skip_invoice_sync=True)._generate_pdf_and_send_invoice(template)

			if order.session_id.state == 'closed':  # If the session isn't closed this isn't needed.
				# If a client requires the invoice later, we need to revers the amount from the closing entry, by making a new entry for that.
				order._create_misc_reversal_move(payment_moves)

		if not moves:
			return {}

		return {
			'name': _('Customer Invoice'),
			'view_mode': 'form',
			'view_id': self.env.ref('account.view_move_form').id,
			'res_model': 'account.move',
			'context': "{'move_type':'out_invoice'}",
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'current',
			'res_id': moves and moves.ids[0] or False,
		}

class account_move_line(models.Model):
	_inherit = 'account.move'


	is_igtf_invoice = fields.Boolean('Is IGTF Invoice',default=False)
	invoice_igtf_amount = fields.Monetary('IGTF Amount')


class account_move_line(models.Model):
	_inherit = 'account.move.line'

	is_igtf_line = fields.Boolean(help="Technical field used to exclude some lines from the invoice_line_ids tab in the form view.")



	
class POSSession(models.Model):
	_inherit = 'pos.session'
 

	def _loader_params_pos_payment_method(self):
		result = super()._loader_params_pos_payment_method()
		result['search_params']['fields'].append('is_igtf')
		return result

	def _loader_params_res_company(self):
		result = super()._loader_params_res_company()
		result["search_params"]["fields"] += ["street", "street2", "zip"]
		return result

	def _loader_params_res_partner(self):
		vals = super()._loader_params_res_partner()
		vals['search_params']['fields'] += ['company_type', 'identification_id']
		return vals

	def _accumulate_amounts(self, data):
		# Accumulate the amounts for each accounting lines group
		# Each dict maps `key` -> `amounts`, where `key` is the group key.
		# E.g. `combine_receivables_bank` is derived from pos.payment records
		# in the self.order_ids with group key of the `payment_method_id`
		# field of the pos.payment record.
		amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0}
		tax_amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0, 'base_amount': 0.0, 'base_amount_converted': 0.0}
		split_receivables_bank = defaultdict(amounts)
		split_receivables_cash = defaultdict(amounts)
		split_receivables_pay_later = defaultdict(amounts)
		combine_receivables_bank = defaultdict(amounts)
		combine_receivables_cash = defaultdict(amounts)
		combine_receivables_pay_later = defaultdict(amounts)
		combine_invoice_receivables = defaultdict(amounts)
		split_invoice_receivables = defaultdict(amounts)
		sales = defaultdict(amounts)
		taxes = defaultdict(tax_amounts)
		stock_expense = defaultdict(amounts)
		stock_return = defaultdict(amounts)
		stock_output = defaultdict(amounts)
		rounding_difference = {'amount': 0.0, 'amount_converted': 0.0}
		# Track the receivable lines of the order's invoice payment moves for reconciliation
		# These receivable lines are reconciled to the corresponding invoice receivable lines
		# of this session's move_id.
		combine_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])
		split_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])
		rounded_globally = self.company_id.tax_calculation_rounding_method == 'round_globally'
		pos_receivable_account = self.company_id.account_default_pos_receivable_account_id
		currency_rounding = self.currency_id.rounding
		closed_orders = self._get_closed_orders()
		for order in closed_orders:
			order_is_invoiced = order.is_invoiced
			for payment in order.payment_ids:
				amount = payment.amount
				if float_is_zero(amount, precision_rounding=currency_rounding):
					continue
				date = payment.payment_date
				payment_method = payment.payment_method_id
				is_split_payment = payment.payment_method_id.split_transactions
				payment_type = payment_method.type

				# If not pay_later, we create the receivable vals for both invoiced and uninvoiced orders.
				#   Separate the split and aggregated payments.
				# Moreover, if the order is invoiced, we create the pos receivable vals that will balance the
				# pos receivable lines from the invoice payments.
				if payment_type != 'pay_later':
					if is_split_payment and payment_type == 'cash':
						split_receivables_cash[payment] = self._update_amounts(split_receivables_cash[payment], {'amount': amount}, date)
					elif not is_split_payment and payment_type == 'cash':
						combine_receivables_cash[payment_method] = self._update_amounts(combine_receivables_cash[payment_method], {'amount': amount}, date)
					elif is_split_payment and payment_type == 'bank':
						split_receivables_bank[payment] = self._update_amounts(split_receivables_bank[payment], {'amount': amount}, date)
					elif not is_split_payment and payment_type == 'bank':
						combine_receivables_bank[payment_method] = self._update_amounts(combine_receivables_bank[payment_method], {'amount': amount}, date)

					# Create the vals to create the pos receivables that will balance the pos receivables from invoice payment moves.
					if order_is_invoiced:
						if is_split_payment:
							split_inv_payment_receivable_lines[payment] |= payment.account_move_id.line_ids.filtered(lambda line: line.account_id == pos_receivable_account)
							split_invoice_receivables[payment] = self._update_amounts(split_invoice_receivables[payment], {'amount': payment.amount}, order.date_order)
						else:
							combine_inv_payment_receivable_lines[payment_method] |= payment.account_move_id.line_ids.filtered(lambda line: line.account_id == pos_receivable_account)
							combine_invoice_receivables[payment_method] = self._update_amounts(combine_invoice_receivables[payment_method], {'amount': payment.amount}, order.date_order)

				# If pay_later, we create the receivable lines.
				#   if split, with partner
				#   Otherwise, it's aggregated (combined)
				# But only do if order is *not* invoiced because no account move is created for pay later invoice payments.
				if payment_type == 'pay_later' and not order_is_invoiced:
					if is_split_payment:
						split_receivables_pay_later[payment] = self._update_amounts(split_receivables_pay_later[payment], {'amount': amount}, date)
					elif not is_split_payment:
						combine_receivables_pay_later[payment_method] = self._update_amounts(combine_receivables_pay_later[payment_method], {'amount': amount}, date)

			if not order_is_invoiced:
				order_taxes = defaultdict(tax_amounts)
				if order.igtf_amount > 0:
					prod = self.env['product.product'].search([('default_code','=','bi_igtf')])
					service_prod_income_account = prod.with_context(with_company=order.company_id.id).property_account_income_id or prod.categ_id.with_context(with_company=order.company_id.id).property_account_income_categ_id
					if not service_prod_income_account:
						raise UserError(_('Please define income account for this product: "%s" (id:%d).')
										% (prod.name, prod.id))
					sale_key1 = (
						# account
						service_prod_income_account.id,
						# sign
						1,
						# for taxes
						tuple(),
						tuple(),
					)   
					sales[sale_key1] = self._update_amounts(sales[sale_key1], {'amount': order.igtf_amount}, order.date_order)
					sales[sale_key1].setdefault('tax_amount', 0.0)

				for order_line in order.lines:
					line = self._prepare_line(order_line)
					# Combine sales/refund lines
					sale_key = (
						# account
						line['income_account_id'],
						# sign
						-1 if line['amount'] < 0 else 1,
						# for taxes
						tuple((tax['id'], tax['account_id'], tax['tax_repartition_line_id']) for tax in line['taxes']),
						line['base_tags'],
					)
					sales[sale_key] = self._update_amounts(sales[sale_key], {'amount': line['amount']}, line['date_order'], round=False)
					sales[sale_key].setdefault('tax_amount', 0.0)
					# Combine tax lines
					for tax in line['taxes']:
						tax_key = (tax['account_id'] or line['income_account_id'], tax['tax_repartition_line_id'], tax['id'], tuple(tax['tag_ids']))
						sales[sale_key]['tax_amount'] += tax['amount']
						order_taxes[tax_key] = self._update_amounts(
							order_taxes[tax_key],
							{'amount': tax['amount'], 'base_amount': tax['base']},
							tax['date_order'],
							round=not rounded_globally
						)
				for tax_key, amounts in order_taxes.items():
					if rounded_globally:
						amounts = self._round_amounts(amounts)
					for amount_key, amount in amounts.items():
						taxes[tax_key][amount_key] += amount

				if self.company_id.anglo_saxon_accounting and order.picking_ids.ids:
					# Combine stock lines
					stock_moves = self.env['stock.move'].sudo().search([
						('picking_id', 'in', order.picking_ids.ids),
						('company_id.anglo_saxon_accounting', '=', True),
						('product_id.categ_id.property_valuation', '=', 'real_time'),
						('product_id.type', '=', 'product'),
					])
					for move in stock_moves:
						exp_key = move.product_id._get_product_accounts()['expense']
						out_key = move.product_id.categ_id.property_stock_account_output_categ_id
						signed_product_qty = move.product_qty
						if move._is_in():
							signed_product_qty *= -1
						amount = signed_product_qty * move.product_id._compute_average_price(0, move.quantity, move)
						stock_expense[exp_key] = self._update_amounts(stock_expense[exp_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
						if move._is_in():
							stock_return[out_key] = self._update_amounts(stock_return[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
						else:
							stock_output[out_key] = self._update_amounts(stock_output[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)

				if self.config_id.cash_rounding:
					diff = order.amount_paid - order.amount_total
					rounding_difference = self._update_amounts(rounding_difference, {'amount': diff}, order.date_order)

				# Increasing current partner's customer_rank
				partners = (order.partner_id | order.partner_id.commercial_partner_id)
				partners._increase_rank('customer_rank')

		if self.company_id.anglo_saxon_accounting:
			global_session_pickings = self.picking_ids.filtered(lambda p: not p.pos_order_id)
			if global_session_pickings:
				stock_moves = self.env['stock.move'].sudo().search([
					('picking_id', 'in', global_session_pickings.ids),
					('company_id.anglo_saxon_accounting', '=', True),
					('product_id.categ_id.property_valuation', '=', 'real_time'),
					('product_id.type', '=', 'product'),
				])
				for move in stock_moves:
					exp_key = move.product_id._get_product_accounts()['expense']
					out_key = move.product_id.categ_id.property_stock_account_output_categ_id
					signed_product_qty = move.product_qty
					if move._is_in():
						signed_product_qty *= -1
					amount = signed_product_qty * move.product_id._compute_average_price(0, move.quantity, move)
					stock_expense[exp_key] = self._update_amounts(stock_expense[exp_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
					if move._is_in():
						stock_return[out_key] = self._update_amounts(stock_return[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
					else:
						stock_output[out_key] = self._update_amounts(stock_output[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
		MoveLine = self.env['account.move.line'].with_context(check_move_validity=False, skip_invoice_sync=True)

		data.update({
			'taxes':                               taxes,
			'sales':                               sales,
			'stock_expense':                       stock_expense,
			'split_receivables_bank':              split_receivables_bank,
			'combine_receivables_bank':            combine_receivables_bank,
			'split_receivables_cash':              split_receivables_cash,
			'combine_receivables_cash':            combine_receivables_cash,
			'combine_invoice_receivables':         combine_invoice_receivables,
			'split_receivables_pay_later':         split_receivables_pay_later,
			'combine_receivables_pay_later':       combine_receivables_pay_later,
			'stock_return':                        stock_return,
			'stock_output':                        stock_output,
			'combine_inv_payment_receivable_lines': combine_inv_payment_receivable_lines,
			'rounding_difference':                 rounding_difference,
			'MoveLine':                            MoveLine,
			'split_invoice_receivables': split_invoice_receivables,
			'split_inv_payment_receivable_lines': split_inv_payment_receivable_lines,
		})
		return data

	