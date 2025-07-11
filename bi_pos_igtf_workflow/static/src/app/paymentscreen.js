/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
// import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos=usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.numberBuffer = useService("number_buffer");
    },
    
    async igtf_tax_calculation(){
        let self = this;
        let currentOrder = this.pos.get_order();
        let orderlines = currentOrder.get_orderlines();                 
        let plines = currentOrder.get_paymentlines();
        let dued = currentOrder.get_due();
        let changed = currentOrder.get_change();
        let client = currentOrder.get_partner();
        let flag = 0;
        let pos_cur =  this.env.services.pos.config.currency_id[0];
        let company_id = this.env.services.pos.config.company_id;
        let igtf_tax= this.env.services.pos.config.igtf_tax;
        let igtf_journal_id=this.env.services.pos.config.igtf_journal_id;
        let call_super = false;
        var igtf_product = self.env.services.pos.db.igtf_product;

        if(orderlines.length === 0){
            call_super = false;
            self.popup.add(ErrorPopup,{
                'title': _t('Empty Order'),
                'body': _t('There must be at least one product in your order before it can be validated.'),
            });

        }
        else{
            call_super=true;
        }
        return call_super;
    },
    deletePaymentLine(cid) {
        var self=this;
        let currentOrder = this.pos.get_order();
        let igtf_tax_amount=0.00;
        currentOrder.set_igtf_amount(igtf_tax_amount)
        super.deletePaymentLine(cid);
    },
    addNewPaymentLine(paymentMethod) {
        let result = this.currentOrder.add_paymentline(paymentMethod);
        let amount = result.amount;
        var self =this;
        let igtf_amount = self.currentOrder.get_igtf_amount();
        let final_amount = amount + igtf_amount;
        result.amount = amount + igtf_amount;
        if (result){
            this.numberBuffer.reset();
            return true;
        }
        else{
            this.popup.add(ErrorPopup, {
                title: _t('Error'),
                body: _t('There is already an electronic payment in progress.'),
            });
            return false;
        }
    },
    async validateOrder(isForceValidate) {
        let check = await this.igtf_tax_calculation();
        if (check){
            super.validateOrder(isForceValidate);
        }
    },

});