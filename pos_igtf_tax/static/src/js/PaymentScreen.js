/** @odoo-module **/
import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";


patch(PaymentScreen.prototype, {
    // @override
    showScreen(name, props){
        let aplicar_igtf = this.pos.config.aplicar_igtf || false;
        if (name === "ProductScreen" && aplicar_igtf && this.paymentLines.some(e=>e.isForeignExchange)){
            this.showPopup('ErrorPopup', {
                title: "Eliminar metodos de pago en divisas.",
                body: "Para poder regresar a la vista de productos debe eliminar los metodos de pago en divisas\r\n para evitar error en el calculo de I.G.T.F"
            });
            return;
        }
        super.showScreen(name, props);
    }
});

