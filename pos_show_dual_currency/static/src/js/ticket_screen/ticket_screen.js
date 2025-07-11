/** @odoo-module */
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    getTotalRef(order) {
        return this.env.utils.formatCurrency(order.get_total_with_tax() * this.pos.config.show_currency_rate,false);
    },
    // Sobrescribir el método que crea las props para OrderWidget
    _getOrderWidgetProps(order) {
        const props = super._getOrderWidgetProps(...arguments);
        return {
            ...props,
            totalRef: order ? order.get_total_with_tax() : 0,
            taxRef: order ? order.get_total_tax() : 0,
        };
    }
});