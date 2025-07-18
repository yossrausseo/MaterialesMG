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
        self.cash_register_balance_start_mn_ref = cashbox_value
        if not self.ref_me_currency_id.is_zero(cashbox_value):
            self.sudo()._post_statement_difference_usd(cashbox_value, opening=True)
        self._post_cash_details_message_usd('Opening Balance Set', cashbox_value, notes)

    def _post_cash_details_message_usd(self, state, difference, notes):
        message = ""
        if difference:
            message = f"{state}: " \
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
        for session in self:
            ref_cash_journal = session.config_id.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and pm.currency_id == session.ref_me_currency_id
            )[:1].journal_id

            if not ref_cash_journal:
                raise UserError(_("There is no cash payment method for the reference currency in this PoS Session"))

            self.env['account.bank.statement.line'].create({
                'pos_session_id': session.id,
                'journal_id': ref_cash_journal.id,
                'amount': sign * amount,
                'date': fields.Date.context_today(self),
                'payment_ref': '-'.join([session.name, extras['translatedType'], reason]),
                'currency_id': session.ref_me_currency_id.id,
            })

        message_content = [f"Cash {extras['translatedType']}", f'- Amount: {extras["formattedAmount"]}']
        if reason:
            message_content.append(f'- Reason: {reason}')
        self.message_post(body='<br/>\n'.join(message_content))

    @api.depends('config_id', 'payment_method_ids')
    def _compute_cash_journal(self):
        super(PosSession, self)._compute_cash_journal()
        for session in self:
            session.me_ref_cash_journal_id = False
            cash_journal_ref = session.payment_method_ids.filtered(
                lambda p: p.is_cash_count and p.currency_id == session.ref_me_currency_id)[:1].journal_id
            if not cash_journal_ref:
                continue
            session.me_ref_cash_journal_id = cash_journal_ref

    def get_closing_control_data(self):
        """
        Solución definitiva que previene el TypeError de forma robusta.
        1. Usa super() para obtener una estructura de props válida y evitar el OwlError.
        2. RECONSTRUYE la lista 'other_payment_methods' desde cero, incluyendo solo
        métodos que NO son de efectivo, para garantizar que no haya datos "sucios".
        3. RECALCULA los detalles del efectivo con la lógica ya validada.
        """
        self.ensure_one()

        # PASO 1: OBTENER LA ESTRUCTURA BASE VÁLIDA DE ODOO.
        closing_control_data = super(PosSession, self).get_closing_control_data()

        # PASO 2: IDENTIFICAR TODOS LOS MÉTODOS DE EFECTIVO QUE NO DEBEN ESTAR EN LA LISTA 'other_payment_methods'.
        # Usamos 'is_cash_count' que es el indicador correcto para el TPV.
        cash_pm_ids = self.payment_method_ids.filtered(lambda pm: pm.is_cash_count).ids
        
        # PASO 3: RECONSTRUIR COMPLETAMENTE 'other_payment_methods' CON DATOS LIMPIOS.
        # Este es el cambio clave que erradica el TypeError.
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'invoiced'])
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != 'pay_later')
        
        clean_other_pms_data = []
        # Iteramos sobre todos los métodos de pago de la sesión.
        for pm in self.payment_method_ids:
            # Si el ID del método actual NO está en nuestra lista de métodos de efectivo...
            if pm.id not in cash_pm_ids:
                # ...entonces es seguro agregarlo a la lista de "otros".
                pm_payments = payments.filtered(lambda p: p.payment_method_id.id == pm.id)
                clean_other_pms_data.append({
                    'id': pm.id,
                    'name': pm.name,
                    'amount': sum(pm_payments.mapped('amount')),
                    'type': pm.type,
                })
        
        # Reemplazamos la lista potencialmente contaminada de super() con nuestra lista 100% limpia.
        closing_control_data['other_payment_methods'] = clean_other_pms_data

        # PASO 4: RECALCULAR LOS DETALLES DE EFECTIVO CON LA LÓGICA QUE YA SABEMOS QUE FUNCIONA.
        main_currency = self.currency_id
        ref_currency = self.ref_me_currency_id
        main_cash_pm = self.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and (not pm.currency_id or pm.currency_id == main_currency)
        )[:1]
        ref_cash_pm = self.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and pm.currency_id == ref_currency
        )[:1]

        # --- Moneda Principal (Bs) ---
        main_cash_payments_amount = sum(payments.filtered(lambda p: p.payment_method_id == main_cash_pm).mapped('amount'))
        main_statement_lines = self.statement_line_ids.filtered(
            lambda st: st.journal_id == self.cash_journal_id and (not st.currency_id or st.currency_id == main_currency)
        )
        main_cash_moves_list = [{'name': move.payment_ref, 'amount': move.amount} for move in main_statement_lines.sorted('create_date')]
        main_cash_moves_amount = sum(move['amount'] for move in main_cash_moves_list)
        expected_amount_main = self.cash_register_balance_start + main_cash_payments_amount + main_cash_moves_amount

        # --- Moneda de Referencia (USD) ---
        ref_cash_payments_amount = sum(payments.filtered(lambda p: p.payment_method_id == ref_cash_pm).mapped('amount'))
        ref_statement_lines = self.statement_line_ids.filtered(
            lambda st: st.currency_id == ref_currency and st.payment_ref != _("Cash In (Opening Balance)")
        )
        ref_cash_moves_list = [{'name': move.payment_ref, 'amount': move.amount} for move in ref_statement_lines.sorted('create_date')]
        ref_cash_moves_amount = sum(move['amount'] for move in ref_cash_moves_list)
        expected_amount_ref = self.cash_register_balance_start_mn_ref + ref_cash_payments_amount + ref_cash_moves_amount
        
        # PASO 5: REEMPLAZAR Y AÑADIR NUESTROS DATOS CALCULADOS EN LA ESTRUCTURA FINAL.
        default_cash_details = {
            'id': main_cash_pm.id if main_cash_pm else None,
            'name': main_cash_pm.name if main_cash_pm else _('Cash'),
            'opening': self.cash_register_balance_start,
            'payment_amount': main_cash_payments_amount,
            'moves': main_cash_moves_list,
            'amount': expected_amount_main,
            'default_cash_details_ref': {
                'id': ref_cash_pm.id if ref_cash_pm else None,
                'name': ref_cash_pm.name if ref_cash_pm else _('Cash (USD)'),
                'opening': self.cash_register_balance_start_mn_ref,
                'payment_amount': ref_cash_payments_amount,
                'moves': ref_cash_moves_list,
                'amount': expected_amount_ref,
            }
        }

        closing_control_data['default_cash_details'] = default_cash_details
        closing_control_data['amount_authorized_diff_ref'] = self.config_id.amount_authorized_diff_ref if self.config_id.cash_control else None
        
        return closing_control_data
    
    def post_closing_cash_details_ref(self, counted_cash):
        print(counted_cash)
        self.cash_register_balance_end_real_mn_ref = counted_cash
        return {'successful': True}

    def _post_statement_difference_usd(self, amount, opening=False):
        self.ensure_one()
        if self.ref_me_currency_id and not self.ref_me_currency_id.is_zero(amount):
            ref_cash_journal = self.config_id.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and pm.currency_id == self.ref_me_currency_id
            )[:1].journal_id

            if not ref_cash_journal:
                raise UserError(_("The reference currency cash journal is not found for %s.", self.ref_me_currency_id.name))

            if opening:
                account_id = ref_cash_journal.profit_account_id
                payment_ref = _("Cash In (Opening Balance)")
                if not account_id:
                     raise UserError(_("Please configure the 'Profit Account' for the journal '%s' to set an opening balance.", ref_cash_journal.name))
            elif amount < 0:
                account_id = ref_cash_journal.loss_account_id
                payment_ref = _("Cash difference observed during the counting (Loss)")
                if not account_id:
                    raise UserError(_("Please configure the 'Loss Account' for the journal '%s'.", ref_cash_journal.name))
            else:
                account_id = ref_cash_journal.profit_account_id
                payment_ref = _("Cash difference observed during the counting (Profit)")
                if not account_id:
                    raise UserError(_("Please configure the 'Profit Account' for the journal '%s'.", ref_cash_journal.name))
            
            self.env['account.bank.statement.line'].create({
                'journal_id': ref_cash_journal.id,
                'amount': amount,
                'date': self.start_at.date() if opening else (self.stop_at.date() if self.stop_at else fields.Date.context_today(self)),
                'payment_ref': payment_ref,
                'pos_session_id': self.id,
                'counterpart_account_id': account_id.id,
                'currency_id': self.ref_me_currency_id.id,
            })
        
    def update_closing_control_state_session_ref(self, notes):
        self._post_cash_details_message_usd('Closing', self.cash_register_difference_ref, notes)

    @api.depends('payment_method_ids', 'order_ids', 'statement_line_ids', 'cash_register_balance_end_real_mn_ref')
    def _compute_cash_balance_ref(self):
        # Hacemos una búsqueda para obtener todos los pagos y líneas de extracto relevantes a la vez
        payments = self.env['pos.payment'].search([('session_id', 'in', self.ids)])
        statement_lines = self.env['account.bank.statement.line'].search([('pos_session_id', 'in', self.ids)])

        # Agrupamos los resultados por session_id para un acceso rápido
        payments_by_session = {s_id: list(p) for s_id, p in groupby(payments, key=lambda p: p.session_id.id)}
        lines_by_session = {s_id: list(l) for s_id, l in groupby(statement_lines, key=lambda l: l.pos_session_id.id)}

        for session in self:
            cash_payment_method_ids = session.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and pm.currency_id == session.ref_me_currency_id
            ).ids

            session_payments = payments_by_session.get(session.id, [])
            total_payment_amount = sum(p.amount for p in session_payments if p.payment_method_id.id in cash_payment_method_ids)

            session_lines = lines_by_session.get(session.id, [])
            total_cash_in_out = sum(l.amount for l in session_lines if l.currency_id == session.ref_me_currency_id)

            session.cash_register_total_entry_encoding_ref = total_payment_amount + total_cash_in_out
            session.cash_register_balance_end_ref = session.cash_register_total_entry_encoding_ref
            session.cash_register_difference_ref = session.cash_register_balance_end_real_mn_ref - session.cash_register_balance_end_ref

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super(PosSession, self)._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)
        self.sudo()._post_statement_difference_usd(self.cash_register_difference_ref)
        return res

    def _loader_params_pos_session(self):
        search_params = super(PosSession, self)._loader_params_pos_session()
        fields = search_params['search_params']['fields']
        fields.append('cash_register_balance_start_mn_ref')
        return search_params

    def action_pos_session_open(self):
        return super(PosSession, self).action_pos_session_open()

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

    @api.model
    def create(self, vals_list):
        new_sessions = super(PosSession, self).create(vals_list)
        for session in new_sessions:
            last_session = self.search([
                ('config_id', '=', session.config_id.id),
                ('state', '=', 'closed'),
                ('id', '!=', session.id)
            ], limit=1, order='stop_at desc')
            if last_session:
                session.cash_register_balance_start_mn_ref = last_session.cash_register_balance_end_real_mn_ref
        return new_sessions

    @api.depends('payment_method_ids', 'order_ids', 'cash_register_balance_start', 'statement_line_ids')
    def _compute_cash_balance(self):
        """
        Calcula el balance de caja esperado únicamente para la moneda principal (ej. Bs).
        Este método ahora filtra de forma estricta para excluir cualquier transacción que pertenezca a una moneda secundaria (ej. USD).
        """
        for session in self:
            main_currency = session.currency_id

            # Pagos de ventas en la moneda principal
            main_cash_payment_methods = session.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and (not pm.currency_id or pm.currency_id.id == main_currency.id)
            )
            total_cash_payment = 0
            if main_cash_payment_methods:
                payments = self.env['pos.payment'].search([
                    ('session_id', '=', session.id),
                    ('payment_method_id', 'in', main_cash_payment_methods.ids)
                ])
                total_cash_payment = sum(payments.mapped('amount'))

            # Movimientos de caja (entradas/salidas) de la moneda principal.
            # La condición clave es "not st.currency_id" o "st.currency_id == main_currency".
            # La apertura en USD tiene un currency_id de USD, por lo que será excluida.
            statement_lines = session.statement_line_ids.filtered(
                lambda st: st.journal_id == session.cash_journal_id and (not st.currency_id or st.currency_id.id == main_currency.id)
            )
            # Excluimos explícitamente las líneas de apertura de la moneda de referencia si por alguna razón se colaron.
            ref_opening_line = statement_lines.filtered(lambda st: st.payment_ref == 'Cash In (Opening Balance)' and st.currency_id)
            total_cash_in_out = sum((statement_lines - ref_opening_line).mapped('amount'))

            session.cash_register_total_entry_encoding = total_cash_in_out + (0.0 if session.state == 'closed' else total_cash_payment)
            session.cash_register_balance_end = session.cash_register_balance_start + session.cash_register_total_entry_encoding
            session.cash_register_difference = session.cash_register_balance_end_real - session.cash_register_balance_end