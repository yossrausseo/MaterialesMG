/** @odoo-module */
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { parseFloat } from "@web/views/fields/parsers";

patch(Orderline.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    },

    price_currency_ref(price) {
        return parseFloat(price.replace(this.pos.currency.symbol, ''));
    }
});