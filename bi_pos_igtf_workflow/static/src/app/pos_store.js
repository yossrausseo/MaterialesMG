/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {


    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        // console.log(order)
        if (order) {
            result.partner = order.get_partner();
            result.invoice_name = order.invoice_name;
            let lines = order.orderlines;
            let totalQuantity = 0;
            for (const line of lines) {
                totalQuantity += line.quantity || 0;
            }
            result.quantityProduct = totalQuantity
        }
        return result;
    },
});
