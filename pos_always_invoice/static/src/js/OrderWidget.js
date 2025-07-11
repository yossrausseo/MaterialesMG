/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
	setup(_defaultObj, options) {
        super.setup(...arguments);
        var self = this;
        self.to_invoice = true;
		self._update_to_invoice();
    },

	_update_to_invoice(){
		this.to_invoice = true;
		console.log('AQUI')
		return this.to_invoice
	}
 
});
