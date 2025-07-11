/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(OrderWidget.prototype, {
	setup() {
		super.setup();
		this.pos = usePos();
		this.total = 0;
		this.tax = 0;
		this.subtotal = 0;
		this.total_amt = 0;
		this.tax_amt = 0;
		this.total_currency_text = '';
		this.taxes_currency_text = '';
		this.total_currency = 0;
		this.taxes_currency = 0;
		this.subtotal_currency_text = '';
		this._updateSummary();
	},

	_updateSummary() {
		let self = this;
		let order = self.pos.get_order();
		if (order) {
			let total = order.get_total_with_tax();
			let tax = order.get_total_with_tax() - order.get_total_without_tax();
			if (this.pos.config.show_dual_currency) {
				let total_currency = 0;
				let taxes_currency = 0;
				let rate_company = parseFloat(this.pos.config.rate_company);
				let show_currency_rate = parseFloat(this.pos.config.show_currency_rate);
				total_currency = show_currency_rate * total / rate_company;
				taxes_currency = show_currency_rate * tax / rate_company;
				let total_currency_text = '';
				let taxes_currency_text = '';
				if (this.pos.config.show_currency_position == 'before') {
					total_currency_text = this.env.utils.formatCurrency(total_currency,false) + ' ' + this.pos.config.show_currency_symbol;
					taxes_currency_text = this.env.utils.formatCurrency(taxes_currency,false) + ' ' + this.pos.config.show_currency_symbol;
				} else {
					total_currency_text = this.env.utils.formatCurrency(total_currency, false) + ' ' + this.pos.config.show_currency_symbol;
					taxes_currency_text = this.env.utils.formatCurrency(taxes_currency, false) + ' ' + this.pos.config.show_currency_symbol;
				}
				this.total_currency = total_currency;
				this.taxes_currency = taxes_currency;
				this.total_amt = total;
				this.tax_amt = tax;
				this.subtotal = this.env.utils.formatCurrency(total - tax);
				this.total = this.env.utils.formatCurrency(total);
				this.total_currency_text = total_currency_text;
				this.tax = this.env.utils.formatCurrency(tax);
				this.taxes_currency_text = taxes_currency_text;
				this.subtotal_currency_text = this.env.utils.formatCurrency((total_currency - taxes_currency),false) + ' ' + this.pos.config.show_currency_symbol;
			} else {
				this.total_amt = total;
				this.tax_amt = tax;
				this.subtotal = this.env.utils.formatCurrency(total - tax);
				this.total = this.env.utils.formatCurrency(total);
				this.tax = this.env.utils.formatCurrency(tax);
			}
		}
	},

	getSubtotal_currency_text() {
		this._updateSummary();
		return this.subtotal_currency_text;
	},

	getTaxes_currency_text() {
		return this.taxes_currency_text;
	},

	getTotal_currency_text() {
		return this.total_currency_text;
	},

	getSubtotal() {
		this._updateSummary();
		return this.subtotal;
	},

	getTax() {
		return this.tax;
	},

	getTotal() {
		return this.total;
	},
});


