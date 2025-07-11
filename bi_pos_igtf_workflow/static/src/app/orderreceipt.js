/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { Component, useEffect, useRef, onMounted } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(OrderReceipt.prototype, {
	setup() {
		super.setup(...arguments);
		this.pos = usePos();
	},
	get igtf_amount(){
		let order = this.pos.get_order();
		let igtf_amount=order.igtf_amount;
		return igtf_amount;
	},
	
});