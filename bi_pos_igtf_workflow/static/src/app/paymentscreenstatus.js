/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
// import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";


patch(PaymentScreenStatus.prototype, {
    setup() {
        super.setup();
        this.pos=usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
    },
    
    get toal_amount_igtf(){
        let igtf_amount = this.props.order.igtf_amount;
        if(igtf_amount){
            return this.env.utils.formatCurrency(
                this.props.order.get_total_with_tax() + this.props.order.get_rounding_applied()
                +igtf_amount);  
        }
        else{
            return this.env.utils.formatCurrency(
                this.props.order.get_total_with_tax() + this.props.order.get_rounding_applied());   
        }

    },
    get totalDueText() {
        let currentOrder = this.pos.get_order();
        if(currentOrder){
            let igtf_amount = currentOrder.igtf_amount;
            let total_amount =this.props.order.get_total_with_tax() +this.props.order.get_rounding_applied();
            if(igtf_amount){
                let total_amount_with_igtf = total_amount + igtf_amount
                return this.env.utils.formatCurrency(total_amount_with_igtf);
            }
            else{
                return this.env.utils.formatCurrency(total_amount);
            }
        }
        else{
            return this.env.utils.formatCurrency(
                this.props.order.get_total_with_tax()+this.props.order.get_rounding_applied()
            );
        }
    },
    get amount_igtf(){
        let currentOrder = this.pos.get_order();
        if(currentOrder){
            let igtf_amount = currentOrder.igtf_amount;
            if(igtf_amount){
                return this.env.utils.formatCurrency(igtf_amount);   
            }
            else{
                return 0.00
            }   
        }
        else{
            return 0.00
        }
    },

});