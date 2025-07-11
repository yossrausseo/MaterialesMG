/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(PaymentScreenPaymentLines.prototype, {
	formatLineAmountUsd(line) {
		return this.env.utils.formatCurrency(line.get_amount() * this.pos.config.show_currency_rate, false);
	}
});

patch(PaymentScreenStatus.prototype, {
	setup() {
		super.setup();
		this.pos = usePos();
	},

	get total_other_currency() {
		let total = this.props.order.get_total_with_tax() + this.props.order.get_rounding_applied()
		let result = total * this.pos.config.show_currency_rate;
		return this.env.utils.formatCurrency(result, false);
	},

	get remainingOtherText() {
		let remaining = this.props.order.get_due() * this.pos.config.show_currency_rate;
		return this.env.utils.formatCurrency(
			remaining > 0 ? remaining : 0, false
		);
	},

	get changeOtherText() {
		let change = this.props.order.get_change() * this.pos.config.show_currency_rate;
		return this.env.utils.formatCurrency(change, false);
	}
});