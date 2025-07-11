/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { onMounted,  onWillUnmount, onWillStart } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        onMounted(() => this.currentOrder.removeIGTF());
        onWillUnmount(() => (!(this.currentOrder.finalized)) && this.removeIgtfAndRelatedPayments());
    },

    deleteForeingPaymets(){
        if (!this.paymentLines.some((line)=> line.isForeignExchange))
            return;
        /*let paymentToDelete = this.paymentLines.filter(line => line.isForeignExchange);
        if (paymentToDelete.length == 0)
            return;
        */
        let paymentToDelete = this.paymentLines.map(line => line.cid);
        // console.log('paymentToDelete', paymentToDelete);
        paymentToDelete.forEach(line_cid => {
            console.log('paymentToDelete', line_cid);
            // this.deletePaymentLine({ detail: { cid: line_cid } });
            this.deletePaymentLine(line_cid);
        })
    },

    removeIgtfAndRelatedPayments(){
        this.currentOrder.removeIGTF();
        this.deleteForeingPaymets();
    },

    // deletePaymentLine(cid) {
    //     const line = this.paymentLines.find((line) => line.cid === cid);
    //     console.log('line', line);
    //     if (["waiting", "waitingCard", "timeout"].includes(line.get_payment_status())) {
    //         line.set_payment_status("waitingCancel");
    //         line.payment_method.payment_terminal
    //             .send_payment_cancel(this.currentOrder, cid)
    //             .then(() => {
    //                 this.currentOrder.remove_paymentline(line);
    //                 this.numberBuffer.reset();
    //             });
    //     } else if (line.get_payment_status() !== "waitingCancel") {
    //         this.currentOrder.remove_paymentline(line);
    //         this.numberBuffer.reset();
    //     }
    // },

    deletePaymentLine(cid) {
        // var self = this;
        const line = this.paymentLines.find((line)=>line.cid === cid);
       
        if (line.isForeignExchange){
            //reviso si quedan otras lineas con moneda extranjera
            let hasOtherforeingPayments = this.paymentLines.some((line)=>line.cid != cid && line.isForeignExchange)
            if (!hasOtherforeingPayments){
                this.currentOrder.removeIGTF();
            }
        }
        console.log('line', line);
        super.deletePaymentLine(cid);
    }
});

patch(ProductScreen.prototype, {
    async clickProduct(product) {
        if(ev.detail.isIgtfProduct) {
            return this.env.services.popup.add(ErrorPopup,{
                title: _t('Invalid action'),
                body: _t('No puedes agregar manualmente el producto IGTF'),
            });
        }
        return super.clickProduct(product);
    }
});
