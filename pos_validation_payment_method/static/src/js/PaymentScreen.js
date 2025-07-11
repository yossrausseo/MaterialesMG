/** @odoo-module **/
import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";


patch(PaymentScreen.prototype, {
    // @override
    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        const change = order.get_change();
        if (change > 0) {
            const changeLines = order.get_paymentlines().filter(line => line.is_change);
            console.log(changeLines)
            const hasChangeMethod = changeLines.some(line => line.payment_method);
            
            //if (!hasChangeMethod) {
            if (changeLines.length == 0) {
                this.popup.add(ErrorPopup, {
                    title: 'Método de pago requerido',
                    body: 'Por favor seleccione un método de pago para el cambio antes de continuar.',
                });
                return false;
            }
        }
        
        return super.validateOrder(...arguments);
    }
});