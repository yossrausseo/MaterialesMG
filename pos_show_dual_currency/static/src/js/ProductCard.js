/** @odoo-module */

import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";

patch(ProductCard.prototype, {
	setup() {
		super.setup();
		this.pos = usePos();
	},
	get price_other_currency() {
		let self = this;
		let prod = this.pos.db.product_by_id[this.props.productId];
		let rate_company  = this.pos.config.rate_company;
		let show_currency_rate =this.pos.config.show_currency_rate;
		let price = prod.get_display_price() * show_currency_rate / rate_company;
		return price
	},
});
