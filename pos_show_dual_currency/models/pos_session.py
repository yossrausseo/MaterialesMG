from collections import defaultdict
from datetime import timedelta
from itertools import groupby

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
from odoo.service.common import exp_version

class PosSession(models.Model):
    _inherit = "pos.session"

    tax_today = fields.Float(string="Tasa Sesión", store=True,
                             compute="_tax_today",
                             tracking=True, digits='Dual_Currency_rate')

    ref_me_currency_id = fields.Many2one('res.currency', related='config_id.show_currency', string="Reference Currency",
                                         store=False)
    cash_register_difference_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string='Ref Before Closing Difference',
        currency_field='ref_me_currency_id',
        help="Difference between the ref theoretical closing balance and the ref real closing balance.",
        readonly=True)

    cash_register_balance_start_mn_ref = fields.Monetary(
        string="Reference Starting Balance",
        currency_field='ref_me_currency_id',
        readonly=True)

    cash_register_balance_end_real_mn_ref = fields.Monetary(
        string="Reference Ending Balance",
        currency_field='ref_me_currency_id',
        readonly=True)
    me_ref_cash_journal_id = fields.Many2one('account.journal', compute='_compute_cash_journal', string='Ref Cash Journal',
                                             store=True)

    cash_register_total_entry_encoding_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string='Ref Total Cash Transaction',
        currency_field='ref_me_currency_id',
        readonly=True)

    cash_register_balance_end_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string="Ref Theoretical Closing Balance",
        currency_field='ref_me_currency_id',
        help="Opening balance summed to all cash transactions.",
        readonly=True)
    cash_real_transaction_ref = fields.Monetary(string='Transaction', currency_field='ref_me_currency_id',
                                                readonly=True)

    def set_cashbox_pos_usd(self, cashbox_value, notes):
        # Asegurar que el valor sea en USD
        if self.ref_me_currency_id != self.env.ref('base.USD'):
            raise UserError(_("La moneda de referencia debe ser USD"))
        
        # Calcular diferencia correctamente
        current_balance = self.cash_register_balance_start_mn_ref or 0.0
        difference = cashbox_value - current_balance
        
        # Actualizar saldo inicial USD
        self.cash_register_balance_start_mn_ref = cashbox_value
        
        # Solo crear ajuste si hay diferencia
        if not float_is_zero(difference, precision_rounding=self.ref_me_currency_id.rounding):
            self.sudo()._post_statement_difference_usd(difference)
        
        self._post_cash_details_message_usd('Opening', difference, notes)
        
    def _post_cash_details_message_usd(self, state, difference, notes):
        message = ""
        if difference:
            message = f"{state} difference: " \
                      f"{self.ref_me_currency_id.symbol + ' ' if self.ref_me_currency_id.position == 'before' else ''}" \
                      f"{self.ref_me_currency_id.round(difference)} " \
                      f"{self.ref_me_currency_id.symbol if self.ref_me_currency_id.position == 'after' else ''}<br/>"
        if notes:
            message += notes.replace('\n', '<br/>')
        if message:
            self.message_post(body=message)

    def _loader_params_res_currency_ref(self):
        currency_id = self.company_id.currency_id.id
        if self.ref_me_currency_id.id:
            currency_id = self.ref_me_currency_id.id
        else:
            if self.config_id.show_currency:
                self.ref_me_currency_id = self.config_id.show_currency.id
                currency_id = self.config_id.show_currency.id
            else:
                if self.company_id.currency_id_dif:
                    self.config_id.show_currency = self.company_id.currency_id_dif.id
                    self.ref_me_currency_id = self.company_id.currency_id_dif.id
                    currency_id = self.company_id.currency_id_dif.id

        return {
            'search_params': {
                'domain': [('id', '=', currency_id)],
                'fields': ['id', 'name', 'symbol', 'position', 'rounding', 'rate', 'decimal_places'],
            },
        }

    def _get_pos_ui_res_currency_ref(self, params):
        res_currency = self.env['res.currency'].search_read(**params['search_params'])
        return res_currency[0]

    def _pos_data_process(self, loaded_data):
        params = self._loader_params_res_currency_ref()
        currency_ref = self._get_pos_ui_res_currency_ref(params)
        loaded_data['res_currency_ref'] = currency_ref
        super(PosSession, self)._pos_data_process(loaded_data)
    
    def try_cash_in_out_ref_currency(self, _type, amount, reason, extras, currency_ref):
        sign = 1 if _type == 'in' else -1
        sessions = self.filtered('me_ref_cash_journal_id')
        if not sessions:
            raise UserError(_("There is no cash payment method for this PoS Session"))
        
        self.env['account.bank.statement.line'].create([
            {
                'pos_session_id': session.id,
                'journal_id': session.me_ref_cash_journal_id.id,
                'amount': sign * amount,
                'date': fields.Date.context_today(self),
                'payment_ref': '-'.join([session.name, extras['translatedType'], reason]),
                'currency_id': session.ref_me_currency_id.id,
            }
            for session in sessions
        ])

        message_content = [f"Cash {extras['translatedType']}", f'- Amount: {extras["formattedAmount"]}']
        if reason:
            message_content.append(f'- Reason: {reason}')
        self.message_post(body='<br/>\n'.join(message_content))
    
    @api.depends('config_id', 'payment_method_ids')
    def _compute_cash_journal(self):
        super(PosSession, self)._compute_cash_journal()
        for session in self:
            session.me_ref_cash_journal_id = False
            
            # Filtrar solo métodos de pago en efectivo que coincidan con la moneda de referencia
            cash_journal_ref = session.payment_method_ids.filtered(
                lambda p: p.is_cash_count and p.currency_id == session.ref_me_currency_id
            )
            
            if cash_journal_ref:
                session.me_ref_cash_journal_id = cash_journal_ref[0].journal_id

    def get_closing_control_data(self):
        closing_control_data = super(PosSession, self).get_closing_control_data()
        self.ensure_one()
        
        # Asegurar estructura básica
        if 'default_cash_details' not in closing_control_data:
            closing_control_data['default_cash_details'] = {
                'name': None,
                'amount': 0,
                'opening': 0,
                'moves': [],
                'payment_amount': 0,
                'id': None,
            }
        
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'invoiced'])
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")

        # Método de pago en USD
        cash_payment_method_ref = self.payment_method_ids.filtered(
            lambda pm: pm.type == 'cash' and pm.currency_id == self.ref_me_currency_id
        )[:1]
        
        # Calcular pagos en USD
        total_ref_payment = 0
        if cash_payment_method_ref:
            total_ref_payment = sum(
                payments.filtered(
                    lambda p: p.payment_method_id == cash_payment_method_ref
                ).mapped('amount_ref')
            )
        
        # Obtener sesión anterior para USD
        last_session_ref = self.search([
            ('config_id', '=', self.config_id.id),
            ('id', '!=', self.id),
            ('state', '=', 'closed')
        ], order='stop_at desc', limit=1) if cash_payment_method_ref else None
        
        # Movimientos de efectivo en USD
        cash_moves_ref = []
        total_moves_ref = 0
        if cash_payment_method_ref:
            for move in self.statement_line_ids.filtered(
                lambda s: s.currency_id == self.ref_me_currency_id and 
                        s.journal_id == self.me_ref_cash_journal_id
            ):
                total_moves_ref += move.amount
                cash_moves_ref.append({
                    'name': move.payment_ref,
                    'amount': move.amount
                })
        
        # Crear objeto para USD
        closing_control_data['default_cash_details_ref'] = {
            'name': cash_payment_method_ref.name if cash_payment_method_ref else "",
            'amount': (last_session_ref.cash_register_balance_end_real_mn_ref if last_session_ref else 0) 
                    + total_ref_payment,
            'opening': self.cash_register_balance_start_mn_ref,
            'moves': cash_moves_ref,
            'payment_amount': total_ref_payment,
            'id': cash_payment_method_ref.id if cash_payment_method_ref else None,
        }
        
        # Propiedad requerida por el frontend
        closing_control_data['amount_authorized_diff_ref'] = (
            self.config_id.amount_authorized_diff_ref 
            if self.config_id.set_maximum_difference 
            else 0
        )
        
        return closing_control_data

    def post_closing_cash_details_ref(self, counted_cash):
        # Solo actualizar si hay un valor válido
        if counted_cash is not None:
            self.cash_register_balance_end_real_mn_ref = counted_cash
        return {'successful': True}
     
    def _post_statement_difference_usd(self, amount):
        if not self.me_ref_cash_journal_id:
            return
            
        # Crear línea contable EN USD
        st_line_vals = {
            'journal_id': self.me_ref_cash_journal_id.id,
            'amount': amount,
            'date': fields.Date.context_today(self),
            'pos_session_id': self.id,
            'currency_id': self.ref_me_currency_id.id,
            'payment_ref': _("Diferencia de cierre USD (%s)") % ('Ganancia' if amount >= 0 else 'Pérdida'),
            'counterpart_account_id': self.me_ref_cash_journal_id.profit_account_id.id if amount >= 0 
                                    else self.me_ref_cash_journal_id.loss_account_id.id,
        }
        self.env['account.bank.statement.line'].create(st_line_vals)
            
        
    def update_closing_control_state_session_ref(self, notes):
        self._post_cash_details_message_usd('Closing', self.cash_register_difference_ref, notes)
    
    @api.depends('payment_method_ids', 'order_ids', 'cash_register_balance_start_mn_ref')
    def _compute_cash_balance_ref(self):
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered(
                lambda p: p.is_cash_count and p.currency_id == session.ref_me_currency_id
            )[:1]
            
            if not cash_payment_method:
                session.cash_register_total_entry_encoding_ref = 0.0
                session.cash_register_balance_end_ref = 0.0
                session.cash_register_difference_ref = 0.0
                continue
                
                
            # SOLO PAGOS EN USD
            total_ref_payment = sum(
                session.env['pos.payment'].search([
                    ('session_id', '=', session.id),
                    ('payment_method_id', '=', cash_payment_method.id),
                    ('currency_id', '=', session.ref_me_currency_id.id)  # Filtro por moneda
                ]).mapped('amount_ref')
            )
            
            last_session = session.search([
                ('config_id', '=', session.config_id.id),
                ('id', '!=', session.id),
                ('state', '=', 'closed')
            ], order='stop_at desc', limit=1)
            
            # SOLO MOVIMIENTOS EN USD
            session.cash_register_total_entry_encoding_ref = (
                sum(session.statement_line_ids.filtered(
                    lambda s: s.currency_id == session.ref_me_currency_id and
                              s.journal_id == session.me_ref_cash_journal_id
                ).mapped('amount')) 
                + (0.0 if session.state == 'closed' else total_ref_payment)
            )
            
            session.cash_register_balance_end_ref = (
                (last_session.cash_register_balance_end_real_mn_ref if last_session else 0.0) 
                + session.cash_register_total_entry_encoding_ref
            )
            
            if session.cash_register_balance_end_real_mn_ref is not False:
                session.cash_register_difference_ref = (
                    session.cash_register_balance_end_real_mn_ref 
                    - session.cash_register_balance_end_ref
                )
            else:
                session.cash_register_difference_ref = 0.0
    
    def close_session_from_ui_ref(self, bank_payment_method_diff_pairs=None):
        bank_payment_method_diffs = dict(bank_payment_method_diff_pairs or [])
        self.ensure_one()
        # Even if this is called in `post_closing_cash_details`, we need to call this here too for case
        # where cash_control = False
        check_closing_session = self._cannot_close_session_ref(bank_payment_method_diffs)
        if check_closing_session:
            return check_closing_session

        validate_result = self.action_pos_session_closing_control_ref(
            bank_payment_method_diffs=bank_payment_method_diffs)

        # If an error is raised, the user will still be redirected to the back end to manually close the session.
        # If the return result is a dict, this means that normally we have a redirection or a wizard => we redirect the user
        if isinstance(validate_result, dict):
            # imbalance accounting entry
            return {
                'successful': False,
                'message': validate_result.get('name'),
                'redirect': True
            }

        self.message_post(body='Point of Sale Session ended')

        return {'successful': True}

    def _cannot_close_session_ref(self, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        if any(order.state == 'draft' for order in self.order_ids):
            return {'successful': False, 'message': _("You cannot close the POS when orders are still in draft"),
                    'redirect': False}
        if self.state == 'closed':
            return {'successful': False, 'message': _("This session is already closed."), 'redirect': True}
        if bank_payment_method_diffs:
            no_loss_account = self.env['account.journal']
            no_profit_account = self.env['account.journal']
            for payment_method in self.env['pos.payment.method'].browse(bank_payment_method_diffs.keys()):
                journal = payment_method.journal_id
                compare_to_zero = self.ref_me_currency_id.compare_amounts(
                    bank_payment_method_diffs.get(payment_method.id), 0)
                if compare_to_zero == -1 and not journal.loss_account_id:
                    no_loss_account |= journal
                elif compare_to_zero == 1 and not journal.profit_account_id:
                    no_profit_account |= journal
            message = ''
            if no_loss_account:
                message += _("Need loss account for the following journals to post the lost amount: %s\n",
                             ', '.join(no_loss_account.mapped('name')))
            if no_profit_account:
                message += _("Need profit account for the following journals to post the gained amount: %s",
                             ', '.join(no_profit_account.mapped('name')))
            if message:
                return {'successful': False, 'message': message, 'redirect': False}

    def action_pos_session_closing_control_ref(self, balancing_account=False, amount_to_balance=0,
                                               bank_payment_method_diffs=None):
        self._check_currency_consistency()
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for session in self:
            if any(order.state == 'draft' for order in session.order_ids):
                raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            session.write({'state': 'closing_control', 'stop_at': fields.Datetime.now()})
            if not session.config_id.cash_control:
                return session.action_pos_session_close_ref(balancing_account, amount_to_balance,
                                                            bank_payment_method_diffs)
            # If the session is in rescue, we only compute the payments in the cash register
            # It is not yet possible to close a rescue session through the front end, see `close_session_from_ui`
            if session.rescue and session.config_id.cash_control:
                default_cash_payment_method_id = self.payment_method_ids.filtered(
                    lambda pm: pm.type == 'cash' and pm.payment_method_id.currency_id == self.ref_me_currency_id)[0]
                orders = self.order_ids.filtered(lambda o: o.state == 'paid' or o.state == 'invoiced')
                total_cash = sum(
                    orders.payment_ids.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped(
                        'amount')
                ) + self.cash_register_balance_start_mn_ref

                session.cash_register_balance_end_real_mn_ref = total_cash

            return session.action_pos_session_validate_ref(balancing_account, amount_to_balance,
                                                           bank_payment_method_diffs)

    def action_pos_session_close_ref(self, balancing_account=False, amount_to_balance=0,
                                     bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        # Session without cash payment method will not have a cash register.
        # However, there could be other payment methods, thus, session still
        # needs to be validated.
        return self._validate_session_ref(balancing_account, amount_to_balance, bank_payment_method_diffs)
        
    def _validate_session_ref(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        
        # Verificar si tenemos diario USD
        if self.me_ref_cash_journal_id and self.ref_me_currency_id:
            # Calcular diferencia en USD
            usd_difference = self.cash_register_difference_ref
            
            # Solo procesar si hay diferencia significativa
            if not float_is_zero(usd_difference, precision_rounding=self.ref_me_currency_id.rounding):
                self.sudo()._post_statement_difference_usd(usd_difference)
        
        # Marcar sesión como cerrada
        self.write({'state': 'closed'})
        return True

    def action_pos_session_validate_ref(self, balancing_account=False, amount_to_balance=0,
                                        bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        return self.action_pos_session_close_ref(balancing_account, amount_to_balance, bank_payment_method_diffs)

    def _loader_params_pos_session(self):
        search_params = super(PosSession, self)._loader_params_pos_session()
        fields = search_params['search_params']['fields']
        fields.append('cash_register_balance_start_mn_ref')
        return search_params

    def action_pos_session_open(self):
        for session in self:
            # Solo manejar USD si existe el diario
            if session.me_ref_cash_journal_id:
                # IMPORTANTE: Mantener USD en su propia moneda
                last_session = self.search([...], order='stop_at desc', limit=1)
                session.cash_register_balance_start_mn_ref = last_session.cash_register_balance_end_real_mn_ref if last_session else 0.0
                
                # NO convertir a Bs
                session.cash_register_balance_start = 0.0  # Forzar 0 en moneda base
            
            super(PosSession, session).action_pos_session_open()
        return True

    @api.depends('config_id')
    def _tax_today(self):
        for rec in self:
            rec.tax_today = 1 / rec.config_id.show_currency_rate if rec.config_id.show_currency_rate > 0 else 1

    def _loader_params_pos_payment_method(self):
        return {
            'search_params': {
                'domain': ['|', ('active', '=', False), ('active', '=', True)],
                'fields': ['name', 'is_cash_count', 'use_payment_terminal', 'split_transactions', 'type','currency_id'],
                'order': 'is_cash_count desc, id',
            },
        }

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        # Create the split and combine cash statement lines and account move lines.
        # `split_cash_statement_lines` maps `journal` -> split cash statement lines
        # `combine_cash_statement_lines` maps `journal` -> combine cash statement lines
        # `split_cash_receivable_lines` maps `journal` -> split cash receivable lines
        # `combine_cash_receivable_lines` maps `journal` -> combine cash receivable lines
        MoveLine = data.get('MoveLine')
        split_receivables_cash = data.get('split_receivables_cash')
        combine_receivables_cash = data.get('combine_receivables_cash')

        # handle split cash payments
        split_cash_statement_line_vals = []
        split_cash_receivable_vals = []
        for payment, amounts in split_receivables_cash.items():
            journal_id = payment.payment_method_id.journal_id.id
            split_cash_statement_line_vals.append(
                self._get_split_statement_line_vals(
                    journal_id,
                    amounts['amount'],
                    payment
                )
            )
            split_cash_receivable_vals.append(
                self._get_split_receivable_vals(
                    payment,
                    amounts['amount'],
                    amounts['amount_converted']
                )
            )
        # handle combine cash payments
        combine_cash_statement_line_vals = []
        combine_cash_receivable_vals = []
        for payment_method, amounts in combine_receivables_cash.items():
            if not float_is_zero(amounts['amount'], precision_rounding=self.currency_id.rounding):
                # USAR MONTO ORIGINAL SIN CONVERSIÓN AUTOMÁTICA
                amount_to_use = amounts['amount']
                
                combine_cash_statement_line_vals.append(
                    self._get_combine_statement_line_vals(
                        payment_method.journal_id.id,
                        amount_to_use,  # Monto original sin conversión
                        payment_method
                    )
                )
                combine_cash_receivable_vals.append(
                    self._get_combine_receivable_vals(
                        payment_method,
                        amounts['amount'],   # Monto original
                        amounts['amount_converted']  # Monto convertido (si es necesario)
                    )
                )

        # create the statement lines and account move lines
        BankStatementLine = self.env['account.bank.statement.line']
        split_cash_statement_lines = {}
        combine_cash_statement_lines = {}
        split_cash_receivable_lines = {}
        combine_cash_receivable_lines = {}
        split_cash_statement_lines = BankStatementLine.create(split_cash_statement_line_vals).mapped(
            'move_id.line_ids').filtered(lambda line: line.account_id.account_type == 'asset_receivable')

        combine_cash_statement_lines = BankStatementLine.create(combine_cash_statement_line_vals).mapped(
            'move_id.line_ids').filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        split_cash_receivable_lines = MoveLine.create(split_cash_receivable_vals)
        combine_cash_receivable_lines = MoveLine.create(combine_cash_receivable_vals)

        data.update(
            {'split_cash_statement_lines': split_cash_statement_lines,
             'combine_cash_statement_lines': combine_cash_statement_lines,
             'split_cash_receivable_lines': split_cash_receivable_lines,
             'combine_cash_receivable_lines': combine_cash_receivable_lines
             })
        return data
        
    