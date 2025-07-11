# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_repr

class ProductProduct(models.Model):
    _inherit = 'product.product'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Diferente', default=lambda self: self.env.company.currency_id_dif.id)

    list_price_usd = fields.Monetary(string="Precio de venta $", currency_field='currency_id_dif')
    standard_price_usd = fields.Float(string="Costo $", company_dependent=True)

    value_usd_svl = fields.Float(compute='_compute_value_usd_svl', compute_sudo=True, company_dependent=True)

    avg_cost_usd = fields.Float(
        string="Costo Promedio (USD)",
        compute="_compute_avg_cost_usd",
        compute_sudo=True,
        help="Costo promedio en USD"
    )
    total_value_usd = fields.Float(
        string="Valor Total (USD)",
        compute="_compute_total_value_usd",
        compute_sudo=True,
        help="Valor total en USD"
    )
    avg_price_usd = fields.Float(
        string="Precio de Venta (USD)",
        compute="_compute_avg_price_usd",
        compute_sudo=True,
        help="Costo promedio en USD"
    )
    total_sale_value_usd = fields.Float(
        string="Valor Venta Total (USD)",
        compute="_compute_total_sale_value_usd",
        compute_sudo=True,
        help="Valor Venta en USD"
    )
    
    @api.depends('standard_price_usd')
    def _compute_avg_cost_usd(self):
        for product in self:
            product.avg_cost_usd = product.standard_price_usd

    @api.depends('standard_price_usd', 'qty_available')
    def _compute_total_value_usd(self):
        for product in self:
            product.total_value_usd = product.standard_price_usd * product.qty_available

    @api.depends('list_price_usd')
    def _compute_avg_price_usd(self):
        for product in self:
            product.avg_price_usd = product.list_price_usd

    @api.depends('list_price_usd', 'qty_available')
    def _compute_total_sale_value_usd(self):
        for product in self:
            product.total_sale_value_usd = product.list_price_usd * product.qty_available

    @api.onchange('list_price_usd')
    def _onchange_list_price_usd(self):
        for rec in self:
            if rec.list_price_usd > 0:
                tasa = self.env.company.currency_id_dif
                if tasa:
                    rec.list_price = rec.list_price_usd * tasa.inverse_rate

    @api.constrains('list_price_usd')
    def _constrains_list_price_usd(self):
        for rec in self:
            if rec.list_price_usd > 0:
                tasa = self.env.company.currency_id_dif
                if tasa:
                    rec.list_price = rec.list_price_usd * tasa.inverse_rate


    def write(self, vals):
        # Si se actualiza list_price_usd en una variante
        if 'list_price_usd' in vals:
            # 1. Obtener la plantilla asociada
            template = self.product_tmpl_id
            
            # 2. Actualizar TODAS las variantes (incluyendo esta) usando SQL crudo
            query = """
                UPDATE product_product
                SET list_price_usd = %s
                WHERE product_tmpl_id = %s
            """
            self.env.cr.execute(query, (vals['list_price_usd'], template.id))
            
            # 3. Actualizar la plantilla también
            template_query = """
                UPDATE product_template
                SET list_price_usd = %s
                WHERE id = %s
            """
            self.env.cr.execute(template_query, (vals['list_price_usd'], template.id))

        return super().write(vals)

    # @api.model
    # def update_list_price_usd_in_variants(self, variants, list_price_usd):
    #     variant_ids = tuple(variants.ids)
        
    #     if variant_ids:
    #         for variant in variants:
    #             self.env.cr.execute("""
    #                 UPDATE product_product
    #                 SET list_price_usd = %s
    #                 WHERE id = %s
    #             """, (list_price_usd, variant.id))

    #         # Confirm the changes
    #         self.env.cr.commit()

    @api.depends('stock_valuation_layer_ids')
    @api.depends_context('to_date', 'company')
    def _compute_value_usd_svl(self):
        """Compute `value_svl` and `quantity_svl`."""
        company_id = self.env.company
        domain = [
            *self.env['stock.valuation.layer']._check_company_domain(company_id),
            ('product_id', 'in', self.ids),
        ]
        if self.env.context.get('to_date'):
            to_date = fields.Datetime.to_datetime(self.env.context['to_date'])
            domain.append(('create_date', '<=', to_date))
        groups = self.env['stock.valuation.layer'].read_group(domain, ['value_usd:sum', 'quantity:sum'], ['product_id'])
        products = self.browse()
        for group in groups:
            product = self.browse(group['product_id'][0])
            product.sudo().with_company(company_id.id).value_usd_svl = self.env.company.currency_id_dif.round(group['value_usd'])
            products |= product
        remaining = (self - products)
        remaining.sudo().with_company(company_id.id).value_usd_svl = 0

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        for rec in self:
            company_id = self.env.company
            if rec.with_company(company_id.id).standard_price_usd and rec.categ_id.property_valuation == 'manual_periodic':
                if rec.with_company(company_id.id).standard_price_usd > 0:
                    tasa = self.env.company.currency_id_dif
                    if tasa:
                        rec.sudo().with_company(company_id.id).standard_price = rec.standard_price_usd / tasa.rate

    def _prepare_in_svl_vals(self, quantity, unit_cost):
        """Prepare the values for a stock valuation layer created by a receipt.

        :param quantity: the quantity to value, expressed in `self.uom_id`
        :param unit_cost: the unit cost to value `quantity`
        :return: values to use in a call to create
        :rtype: dict
        """
        self.ensure_one()
        tasa = self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)
        unit_cost_usd = float(unit_cost) / tasa.rate
        vals = {
            'product_id': self.id,
            'value': unit_cost * quantity,
            #'value_usd': unit_cost_usd * quantity,
            'unit_cost': unit_cost,
            #'unit_cost_usd': unit_cost_usd,
            'quantity': quantity,
        }
        if self.cost_method in ('average', 'fifo'):
            vals['remaining_qty'] = quantity
            vals['remaining_value'] = vals['value']
            #vals['remaining_value_usd'] = vals['value_usd']
        return vals

    def _prepare_out_svl_vals(self, quantity, company):
        """Prepare the values for a stock valuation layer created by a delivery.

        :param quantity: the quantity to value, expressed in `self.uom_id`
        :return: values to use in a call to create
        :rtype: dict
        """
        self.ensure_one()
        # Quantity is negative for out valuation layers.
        quantity = -1 * quantity
        if self.standard_price_usd > 0:
            tasa_tmp = round(self.standard_price / self.standard_price_usd, 4)
        else:
            tasa_tmp = 1
        vals = {
            'product_id': self.id,
            'value': quantity * self.standard_price,
            'value_usd': quantity * self.standard_price_usd,
            'unit_cost': self.standard_price,
            'tasa': tasa_tmp,
            'unit_cost_usd': self.standard_price_usd,
            'quantity': quantity,
        }
        if self.cost_method in ('average', 'fifo'):
            fifo_vals = self._run_fifo(abs(quantity), company)
            vals['remaining_qty'] = fifo_vals.get('remaining_qty')
            # In case of AVCO, fix rounding issue of standard price when needed.
            if self.cost_method == 'average':
                currency = self.env.company.currency_id
                rounding_error = currency.round(self.standard_price * self.quantity_svl - self.value_svl)
                if rounding_error:
                    # If it is bigger than the (smallest number of the currency * quantity) / 2,
                    # then it isn't a rounding error but a stock valuation error, we shouldn't fix it under the hood ...
                    if abs(rounding_error) <= (abs(quantity) * currency.rounding) / 2:
                        vals['value'] += rounding_error
                        vals['rounding_adjustment'] = '\nRounding Adjustment: %s%s %s' % (
                            '+' if rounding_error > 0 else '',
                            float_repr(rounding_error, precision_digits=currency.decimal_places),
                            currency.symbol
                        )
            if self.cost_method == 'fifo':
                vals.update(fifo_vals)
        return vals

    def _run_fifo(self, quantity, company):
        self.ensure_one()

        # Find back incoming stock valuation layers (called candidates here) to value `quantity`.
        qty_to_take_on_candidates = quantity
        candidates = self.env['stock.valuation.layer'].sudo().search([
            ('product_id', '=', self.id),
            ('remaining_qty', '>', 0),
            ('company_id', '=', company.id),
        ])
        new_standard_price = 0
        new_standard_price_usd = 0
        tmp_value = 0  # to accumulate the value taken on the candidates
        tmp_value_usd = 0
        for candidate in candidates:
            qty_taken_on_candidate = min(qty_to_take_on_candidates, candidate.remaining_qty)

            candidate_unit_cost = candidate.remaining_value / candidate.remaining_qty
            candidate_unit_cost_usd = candidate.remaining_value_usd / candidate.remaining_qty
            new_standard_price = candidate_unit_cost
            new_standard_price_usd = candidate_unit_cost_usd
            value_taken_on_candidate = qty_taken_on_candidate * candidate_unit_cost
            value_taken_on_candidate_usd = qty_taken_on_candidate * candidate_unit_cost_usd
            value_taken_on_candidate = candidate.currency_id.round(value_taken_on_candidate)
            new_remaining_value = candidate.remaining_value - value_taken_on_candidate
            new_remaining_value_usd = candidate.remaining_value_usd - value_taken_on_candidate_usd
            candidate_vals = {
                'remaining_qty': candidate.remaining_qty - qty_taken_on_candidate,
                'remaining_value': new_remaining_value,
                'remaining_value_usd': new_remaining_value_usd,
            }

            candidate.write(candidate_vals)

            qty_to_take_on_candidates -= qty_taken_on_candidate
            tmp_value += value_taken_on_candidate
            tmp_value_usd += value_taken_on_candidate_usd

            if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
                if float_is_zero(candidate.remaining_qty, precision_rounding=self.uom_id.rounding):
                    next_candidates = candidates.filtered(lambda svl: svl.remaining_qty > 0)
                    new_standard_price = next_candidates and next_candidates[0].unit_cost or new_standard_price
                    new_standard_price_usd = next_candidates and next_candidates[0].unit_cost_usd or new_standard_price_usd
                break

        # Update the standard price with the price of the last used candidate, if any.
        if new_standard_price and self.cost_method == 'fifo':
            self.sudo().with_company(company.id).with_context(disable_auto_svl=True).standard_price = new_standard_price
        if new_standard_price_usd and self.cost_method == 'fifo':
            self.sudo().with_company(company.id).with_context(disable_auto_svl=True).standard_price_usd = new_standard_price_usd

        # If there's still quantity to value but we're out of candidates, we fall in the
        # negative stock use case. We chose to value the out move at the price of the
        # last out and a correction entry will be made once `_fifo_vacuum` is called.
        vals = {}
        if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
            if tmp_value > 0:
                tasa_tmp = round(tmp_value_usd / tmp_value, 4)
            else:
                tasa_tmp = 1
            vals = {
                'value': -tmp_value,
                'value_usd': -tmp_value_usd,
                'unit_cost': tmp_value / quantity,
                'tasa': tasa_tmp,
                'unit_cost_usd': tmp_value_usd / quantity,
            }
        else:

            assert qty_to_take_on_candidates > 0
            last_fifo_price = new_standard_price or self.standard_price
            last_fifo_price_usd = new_standard_price_usd or self.standard_price_usd
            negative_stock_value = last_fifo_price * -qty_to_take_on_candidates
            negative_stock_value_usd = last_fifo_price_usd * -qty_to_take_on_candidates
            tmp_value += abs(negative_stock_value)
            tmp_value_usd += abs(negative_stock_value_usd)
            vals = {
                'remaining_qty': -qty_to_take_on_candidates,
                'value': -tmp_value,
                'unit_cost': last_fifo_price,
                'value_usd': -tmp_value_usd,
                'unit_cost_usd': last_fifo_price_usd,
            }
        return vals

    def price_compute(self, price_type, uom=False, currency=False, company=None, date=False):
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        self = self.with_company(company)
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            self = self.sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for product in self:
            prices[product.id] = product[price_type if not price_type == 'standard_price' else 'standard_price_usd'] or 0.0
            if price_type == 'standard_price':
                prices[product.id] = prices[product.id] * self.env.company.currency_id_dif.rate
            if price_type == 'list_price':
                prices[product.id] += product.price_extra
                # we need to add the price from the attributes that do not generate variants
                # (see field product.attribute create_variant)
                if self._context.get('no_variant_attributes_price_extra'):
                    # we have a list of price_extra that comes from the attribute values, we need to sum all that
                    prices[product.id] += sum(self._context.get('no_variant_attributes_price_extra'))

            if uom:
                prices[product.id] = product.uom_id._compute_price(prices[product.id], uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            #if currency:
            #    price = price_currency._convert(price, currency, company, date)

        return prices