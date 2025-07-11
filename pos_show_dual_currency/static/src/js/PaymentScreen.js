// /** @odoo-module */
// import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
// import { patch } from "@web/core/utils/patch";
// import { usePos } from "@point_of_sale/app/store/pos_hook";

// patch(PaymentScreen.prototype, {
//     setup() {
//         super.setup();
//         this.pos = usePos();
//     },

//     _updateSelectedPaymentline() {
//         const rateCompany = this.pos.config.rate_company;
//         const showCurrencyRate = this.pos.config.show_currency_rate;
        
//         // Actualizar líneas de pago si todas están pagadas
//         if (this.paymentLines.every(line => line.paid)) {
//             this.currentOrder.add_paymentline(this.pos.payment_methods[0]);
//         }
        
//         if (!this.selectedPaymentLine) return;

//         // Verificar terminal de pago
//         const paymentTerminal = this.selectedPaymentLine.payment_method.payment_terminal;
//         if (paymentTerminal && !['pending', 'retry'].includes(this.selectedPaymentLine.get_payment_status())) {
//             return;
//         }

//         // Manejar el buffer numérico
//         if (NumberBuffer.get() === null) {
//             this.deletePaymentLine({ detail: { cid: this.selectedPaymentLine.cid } });
//         } else {
//             let convertedAmount = NumberBuffer.getFloat();
            
//             // Conversión de moneda
//             if (this.selectedPaymentLine.payment_method.pago_usd) {
//                 if (rateCompany > showCurrencyRate) {
//                     convertedAmount = (convertedAmount * rateCompany) / showCurrencyRate;
//                 } else if (rateCompany < showCurrencyRate) {
//                     convertedAmount *= rateCompany;
//                 }
//                 this.selectedPaymentLine.set_usd_amt(NumberBuffer.getFloat());
//             }
            
//             this.selectedPaymentLine.set_amount(convertedAmount);
//         }
//     }
// });