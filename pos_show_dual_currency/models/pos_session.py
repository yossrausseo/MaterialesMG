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

    def set_cashbox_pos_usd(self, counted_amount, notes):
        """
        Este método ahora calcula la diferencia entre el conteo manual y el saldo
        inicial esperado, y registra únicamente ese ajuste.
        """
        self.ensure_one()

        # Guardamos el conteo real en su propio campo para futura referencia.
        self.cash_register_balance_end_real_mn_ref = counted_amount # Usamos este campo para almacenar el conteo real de apertura.

        # Calcula la diferencia (el ajuste)
        adjustment_amount = counted_amount - self.cash_register_balance_start_mn_ref

        # Si hay una diferencia, la registramos usando nuestra nueva función.
        if not self.ref_me_currency_id.is_zero(adjustment_amount):
            self.sudo()._post_opening_adjustment_usd(adjustment_amount)

        # El mensaje en el chatter ahora reflejará el ajuste, no el total.
        self._post_cash_details_message_usd('Opening Balance Adjustment', adjustment_amount, notes)

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
        Versión final y blindada. Se ajustan los filtros de las líneas de extracto
        para que sean inequívocos, basándose tanto en el diario como en la presencia
        (o ausencia) de una moneda específica.
        """
        self.ensure_one()

        # --- 1. OBTENER DATOS BASE ---
        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != 'pay_later')
        main_currency = self.currency_id
        ref_currency = self.ref_me_currency_id

        # --- 2. IDENTIFICAR MÉTODOS Y DIARIOS DE PAGO POR TIPO ---
        ref_cash_pm = self.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and pm.currency_id == ref_currency
        )[:1]
        
        main_cash_pms = self.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and pm.currency_id != ref_currency
        )
        
        non_cash_pms = self.payment_method_ids.filtered(lambda pm: not pm.is_cash_count)

        # --- 3. CÁLCULO AGREGADO PARA MONEDA PRINCIPAL (Bs) ---
        main_cash_payments = payments.filtered(lambda p: p.payment_method_id.id in main_cash_pms.ids)
        main_cash_payments_amount = sum(main_cash_payments.mapped('amount'))

        # Filtro estricto: Pertenece al diario principal Y NO tiene moneda extranjera.
        main_cash_journal_id = self.cash_journal_id.id
        main_statement_lines = self.statement_line_ids.filtered(
            lambda st: st.journal_id.id == main_cash_journal_id and not st.currency_id
        )
        
        main_cash_moves_amount = sum(main_statement_lines.mapped('amount'))
        main_cash_moves_list = [{'name': move.payment_ref, 'amount': move.amount} for move in main_statement_lines.sorted('create_date')]
        
        expected_amount_main = self.cash_register_balance_start + main_cash_payments_amount + main_cash_moves_amount

        main_pm_label = main_cash_pms[0].name if main_cash_pms else _('Cash')
        
        default_cash_details = {
            'id': main_cash_pms[0].id if main_cash_pms else None,
            'name': main_pm_label,
            'opening': self.cash_register_balance_start,
            'payment_amount': main_cash_payments_amount,
            'moves': main_cash_moves_list,
            'amount': expected_amount_main,
        }

        # --- 4. CÁLCULO PARA MONEDA DE REFERENCIA (USD) ---
        ref_cash_payments_amount = 0.0
        if ref_cash_pm:
            rate = self.tax_today if self.tax_today > 0 else 1
            ref_cash_payments = payments.filtered(lambda p: p.payment_method_id == ref_cash_pm)
            ref_cash_payments_amount = sum(p.amount / rate for p in ref_cash_payments)

        # Filtro estricto: Pertenece al diario de referencia Y TIENE la moneda de referencia.
        ref_journal_id = ref_cash_pm.journal_id.id if ref_cash_pm else None
        ref_statement_lines = self.statement_line_ids.filtered(
            lambda st: st.journal_id.id == ref_journal_id and st.currency_id == ref_currency
        )

        ref_cash_moves_list = [{'name': move.payment_ref, 'amount': move.amount} for move in ref_statement_lines.sorted('create_date')]
        ref_cash_moves_amount = sum(ref_statement_lines.mapped('amount'))
        
        expected_amount_ref = self.cash_register_balance_start_mn_ref + ref_cash_payments_amount + ref_cash_moves_amount

        default_cash_details['default_cash_details_ref'] = {
            'id': ref_cash_pm.id if ref_cash_pm else None,
            'name': ref_cash_pm.name if ref_cash_pm else _('Cash (USD)'),
            'opening': self.cash_register_balance_start_mn_ref,
            'payment_amount': ref_cash_payments_amount,
            'moves': ref_cash_moves_list,
            'amount': expected_amount_ref,
        }

        # --- 5. CÁLCULO DE OTROS MÉTODOS DE PAGO (NO EFECTIVO) ---
        other_payment_methods_data = []
        for pm in non_cash_pms:
            other_payments = payments.filtered(lambda p: p.payment_method_id == pm)
            other_payment_methods_data.append({
                'name': pm.name,
                'amount': sum(other_payments.mapped('amount')),
                'number': len(other_payments),
                'id': pm.id,
                'type': pm.type,
            })

        # --- 6. CONSTRUCCIÓN DEL DICCIONARIO FINAL ---
        return {
            'orders_details': {
                'quantity': len(orders),
                'amount': sum(orders.mapped('amount_total'))
            },
            'opening_notes': self.opening_notes,
            'default_cash_details': default_cash_details,
            'other_payment_methods': other_payment_methods_data,
            'is_manager': self.user_has_groups("point_of_sale.group_pos_manager"),
            'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None,
            'amount_authorized_diff_ref': self.config_id.amount_authorized_diff_ref if self.config_id.cash_control else None,
        }
    
    def post_closing_cash_details_ref(self, counted_cash):
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
        
    @api.depends('statement_line_ids', 'order_ids.payment_ids.amount', 'cash_register_balance_start')
    def _compute_cash_balance(self):
        """
        Versión corregida que emula la lógica nativa de Odoo, incluyendo tanto los pagos
        de los pedidos como las líneas de extracto manuales en el cálculo del balance teórico.
        """
        for session in self:
            if not session.config_id.cash_control:
                session.cash_register_total_entry_encoding = 0.0
                session.cash_register_balance_end = 0.0
                session.cash_register_difference = 0.0
                continue

            # 1. Obtener pagos en efectivo de la moneda principal desde las órdenes (lógica nativa)
            main_cash_pm = session.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and pm.currency_id != session.ref_me_currency_id
            )
            # Asegurarse de que el método de pago existe antes de buscar los pagos.
            total_cash_payment = 0.0
            if main_cash_pm:
                payment_data = self.env['pos.payment']._read_group(
                    [('session_id', '=', session.id), ('payment_method_id', 'in', main_cash_pm.ids)],
                    aggregates=['amount:sum']
                )
                if payment_data and payment_data[0][0]:
                    total_cash_payment = payment_data[0][0]

            # 2. Obtener movimientos manuales de efectivo de la moneda principal (tu lógica de filtro)
            statement_lines = session.statement_line_ids.filtered(
                lambda st: st.journal_id == session.cash_journal_id and not st.currency_id
            )
            total_manual_moves = sum(statement_lines.mapped('amount'))

            # 3. Sumar ambos para obtener el total de transacciones
            total_entry_encoding = total_manual_moves + total_cash_payment
            session.cash_register_total_entry_encoding = total_entry_encoding

            # 4. Calcular el balance teórico y la diferencia
            # En sesiones no cerradas, el balance teórico es el inicial más todas las transacciones.
            session.cash_register_balance_end = session.cash_register_balance_start + total_entry_encoding
            session.cash_register_difference = session.cash_register_balance_end_real - session.cash_register_balance_end
            
    @api.depends('statement_line_ids.amount', 'cash_register_balance_start_mn_ref')
    def _compute_cash_balance_ref(self):
        """
        Versión final y correcta para la moneda de referencia. Lógica simétrica.
        """
        for session in self:
            if not session.config_id.cash_control or not session.ref_me_currency_id:
                session.cash_register_total_entry_encoding_ref = 0.0
                session.cash_register_balance_end_ref = 0.0
                session.cash_register_difference_ref = 0.0
                continue

            ref_cash_pm = session.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count and pm.currency_id == session.ref_me_currency_id
            )
            if not ref_cash_pm:
                continue
                
            ref_journal = ref_cash_pm.journal_id
            statement_lines = session.statement_line_ids.filtered(
                lambda st: st.journal_id == ref_journal and st.currency_id == session.ref_me_currency_id
            )
            total_cash_in_out_ref = sum(statement_lines.mapped('amount'))

            session.cash_register_total_entry_encoding_ref = total_cash_in_out_ref
            session.cash_register_balance_end_ref = session.cash_register_balance_start_mn_ref + total_cash_in_out_ref
            session.cash_register_difference_ref = session.cash_register_balance_end_real_mn_ref - session.cash_register_balance_end_ref
    
    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """
        Sobrescritura completa y final que controla el flujo de validación.
        No se llama al _post_statement_difference nativo, sino que se controla
        explícitamente el registro de diferencias de ambas monedas.
        """
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()

        self._check_if_no_draft_orders()
        self._check_invoices_are_posted()

        # 1. Crear el asiento contable principal y TODAS las líneas de extracto de los pagos.
        data = self.with_company(self.company_id)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)

        # 2. Forzar recálculo. Ahora los campos 
        self.invalidate_recordset(['cash_register_difference', 'cash_register_difference_ref'])
        
        # 3. Registrar las diferencias REALES de cierre, si las hay.
        if not self.currency_id.is_zero(self.cash_register_difference):
            self.sudo()._post_statement_difference(self.cash_register_difference, is_opening=False)
        
        if self.ref_me_currency_id and not self.ref_me_currency_id.is_zero(self.cash_register_difference_ref):
            self.sudo()._post_statement_difference_usd(self.cash_register_difference_ref, opening=False)

        # 4. Continuar con el resto del proceso nativo (publicar asiento, reconciliar, etc.)
        if self.move_id.line_ids:
            self.move_id.sudo().with_company(self.company_id)._post()
            self.env['pos.order'].search([('session_id', '=', self.id), ('state', '=', 'paid')]).write({'state': 'done'})
        else:
            self.move_id.sudo().unlink()
        
        self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        self.write({'state': 'closed'})
        return True
    
    def _loader_params_pos_session(self):
        search_params = super(PosSession, self)._loader_params_pos_session()
        fields = search_params['search_params']['fields']
        fields.append('cash_register_balance_start_mn_ref')
        return search_params

    def action_pos_session_open(self):
        """
        Extiende el método nativo para crear automáticamente la línea de extracto
        correspondiente al saldo de apertura heredado de la moneda de referencia.
        """
        # Llama al método original para que la sesión cambie a estado 'opened'.
        res = super(PosSession, self).action_pos_session_open()

        for session in self.filtered(lambda s: s.state == 'opened' and not s.rescue):
            # Si hay un saldo inicial en la moneda de referencia...
            if session.ref_me_currency_id and not session.ref_me_currency_id.is_zero(session.cash_register_balance_start_mn_ref):
                
                # Verificamos si ya existe una línea de apertura para no duplicarla.
                # Esto es una protección extra si el método se ejecuta más de una vez.
                existing_line = self.env['account.bank.statement.line'].search([
                    ('pos_session_id', '=', session.id),
                    ('currency_id', '=', session.ref_me_currency_id.id),
                    ('payment_ref', '=', _("Cash In (Opening Balance)"))
                ], limit=1)

                if not existing_line:
                    session.sudo()._post_statement_difference_usd(
                        session.cash_register_balance_start_mn_ref,
                        opening=True
                    )
        return res
    
    def _post_opening_adjustment_usd(self, amount):
        """
        Crea una línea de extracto específicamente para los ajustes de efectivo
        (sobrantes o faltantes) durante la apertura de la sesión.
        """
        self.ensure_one()
        ref_cash_journal = self.config_id.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and pm.currency_id == self.ref_me_currency_id
        )[:1].journal_id

        if not ref_cash_journal:
            raise UserError(_("The reference currency cash journal is not found for %s.", self.ref_me_currency_id.name))

        # Determina la cuenta y la etiqueta según si es un sobrante o un faltante.
        if amount < 0:
            account_id = ref_cash_journal.loss_account_id
            payment_ref = _("Opening Balance Adjustment")
            if not account_id:
                raise UserError(_("Please configure the 'Loss Account' for the journal '%s'.", ref_cash_journal.name))
        else:
            account_id = ref_cash_journal.profit_account_id
            payment_ref = _("Opening Balance Adjustment")
            if not account_id:
                raise UserError(_("Please configure the 'Profit Account' for the journal '%s'.", ref_cash_journal.name))

        self.env['account.bank.statement.line'].create({
            'journal_id': ref_cash_journal.id,
            'amount': amount,
            'date': self.start_at.date() if self.start_at else fields.Date.context_today(self),
            'payment_ref': payment_ref,
            'pos_session_id': self.id,
            'counterpart_account_id': account_id.id,
            'currency_id': self.ref_me_currency_id.id,
        })

    @api.depends('config_id')
    def _tax_today(self):
        for rec in self:
            rec.tax_today = 1 / rec.config_id.show_currency_rate if rec.config_id.show_currency_rate > 0 else 1

    def _loader_params_pos_payment_method(self):
        # Llama al método original para obtener los parámetros base.
        params = super()._loader_params_pos_payment_method()
        
        # Añade 'currency_id' a la lista de campos si no está ya.
        # Usamos un set para evitar duplicados.
        fields_set = set(params['search_params']['fields'])
        fields_set.add('currency_id')
        params['search_params']['fields'] = list(fields_set)
        
        fields_set.add('is_cash_count')
        params['search_params']['fields'] = list(fields_set)

        return params
    
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

            
    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        """
        Sobrescritura del método nativo para manejar correctamente la creación de líneas de
        extracto para ambas monedas de efectivo.
        """
        # Obtenemos los pagos en efectivo que el proceso de validación ya ha acumulado.
        split_receivables_cash = data.get('split_receivables_cash', {})
        combine_receivables_cash = data.get('combine_receivables_cash', {})
        ref_currency = self.ref_me_currency_id

        # --- 1. SEPARAMOS LOS PAGOS POR MONEDA ---
        main_currency_split = {}
        ref_currency_split = {}
        for payment, amounts in split_receivables_cash.items():
            if payment.payment_method_id.currency_id == ref_currency:
                ref_currency_split[payment] = amounts
            else:
                main_currency_split[payment] = amounts

        main_currency_combine = {}
        ref_currency_combine = {}
        for pm, amounts in combine_receivables_cash.items():
            if pm.currency_id == ref_currency:
                ref_currency_combine[pm] = amounts
            else:
                main_currency_combine[pm] = amounts

        # --- 2. DEJAMOS QUE EL PROCESO NATIVO MANEJE LA MONEDA PRINCIPAL ---
        # Pasamos solo los pagos de la moneda principal (Bs) al método original.
        data['split_receivables_cash'] = main_currency_split
        data['combine_receivables_cash'] = main_currency_combine
        data = super(PosSession, self)._create_cash_statement_lines_and_cash_move_lines(data)

        # --- 3. PROCESAMOS MANUALMENTE LA MONEDA DE REFERENCIA (USD) ---
        BankStatementLine = self.env['account.bank.statement.line']
        MoveLine = data.get('MoveLine')
        rate = self.tax_today if self.tax_today > 0 else 1

        # Creamos las líneas para los pagos en USD, usando el importe correcto.
        statement_line_vals = []
        receivable_vals = []

        # (Manejamos pagos "split", que es el caso más común con cliente identificado)
        for payment, amounts in ref_currency_split.items():
            # ¡La corrección clave! Calculamos el importe real en USD.
            amount_in_ref_currency = amounts['amount'] / rate
            
            # Valores para la línea de extracto (la que ves en la imagen)
            statement_line_vals.append(
                self._get_split_statement_line_vals(
                    payment.payment_method_id.journal_id.id,
                    amount_in_ref_currency, # Usamos el importe correcto en USD
                    payment
                )
            )
            # Valores para el asiento contable de contrapartida
            receivable_vals.append(
                self._get_split_receivable_vals(
                    payment,
                    amounts['amount'], # El `amount` en Bs para la línea de asiento
                    amounts['amount_converted'] # El `amount_converted` en moneda de la compañía
                )
            )
        
        # (Y también para pagos "combine" por si se usan)
        for pm, amounts in ref_currency_combine.items():
            amount_in_ref_currency = amounts['amount'] / rate
            statement_line_vals.append(
                self._get_combine_statement_line_vals(
                    pm.journal_id.id,
                    amount_in_ref_currency, # Usamos el importe correcto en USD
                    pm
                )
            )
            receivable_vals.append(
                self._get_combine_receivable_vals(
                    pm,
                    amounts['amount'],
                    amounts['amount_converted']
                )
            )

        if statement_line_vals:
            # Creamos las nuevas líneas de extracto y asientos
            ref_statement_lines = BankStatementLine.create(statement_line_vals)
            ref_receivable_lines = MoveLine.create(receivable_vals)

            # Las añadimos al diccionario de datos para que el proceso de reconciliación las encuentre.
            data['split_cash_statement_lines'] = data.get('split_cash_statement_lines', self.env['account.move.line']) | ref_statement_lines.mapped('move_id.line_ids').filtered(lambda line: line.account_id.account_type == 'asset_receivable')
            data['split_cash_receivable_lines'] = data.get('split_cash_receivable_lines', self.env['account.move.line']) | ref_receivable_lines

        return data