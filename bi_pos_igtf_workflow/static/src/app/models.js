/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import {
    formatFloat,
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";

// New orders are now associated with the current table, if any.

patch(Order.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        var self = this;
        self.igtf_amount = self.igtf_amount || "";
    },
    
    set_igtf_amount(igtf_amount){
        if(igtf_amount){
            this.igtf_amount = igtf_amount; 
        }
        else{
            this.igtf_amount  = 0.00;
        }
        
    },
    get_igtf_amount(){
        let self = this;
        let currentOrder = this.pos.get_order();
        let plines = this.get_paymentlines();
        let igtf_tax= this.pos.config.igtf_tax;
        var rounding = this.pos.currency.rounding;
        let igtf_tax_amount = 0.00;

        for (let i = 0; i < plines.length; i++) {
            if (plines[i].payment_method.is_igtf === true) {
                let amount = plines[i].amount
                igtf_tax_amount = (amount * igtf_tax)/100;
                console.log(igtf_tax_amount)
                /*plines[i].amount=igtf_tax_amount;*/
                self.set_igtf_amount(igtf_tax_amount)

            }
        }
        return round_pr(igtf_tax_amount, rounding);     
    },
    init_from_JSON(json){
        super.init_from_JSON(...arguments); 
        var self=this;
        self.igtf_amount = json.igtf_amount | 0.0;
        self.amount_total = json.amount_total || 0.0;
    },
    export_as_JSON(){
        var self = this;
        var loaded=super.export_as_JSON(...arguments);
        let currentOrder = this.pos.get_order();
        if(currentOrder){
            let igtf_amount= currentOrder.igtf_amount;
            loaded.igtf_amount =currentOrder.igtf_amount;
            loaded.amount_total = igtf_amount + this.get_total_with_tax();
        }
        else{
            loaded.igtf_amount = 0.00 ;
            loaded.amount_total =this.get_total_with_tax();
        }
        return loaded;
    },
    get_change(paymentline){
        // var rounding = this.pos.currency.rounding;
        let currentOrder = this.pos.get_order();
        let igtf_amount = 0.0;
        if(currentOrder){
            igtf_amount= currentOrder.igtf_amount   
        }
        else{
            igtf_amount = 0.0;
        }
        if (!paymentline) {
            var change = this.get_total_paid() - (this.get_total_with_tax() + igtf_amount) - this.get_rounding_applied();
        } else {
            var change = -(this.get_total_with_tax()); 
            var lines  = this.paymentlines.models;
            for (var i = 0; i < lines.length; i++) {
                change += lines[i].get_amount();
                if (lines[i] === paymentline) {
                    break;
                }
            }
        }
        return round_pr(Math.max(0,change), this.pos.currency.rounding);
    },
    get_due(paymentline){
        let currentOrder = this.pos.get_order();
        let igtf_amount = 0.0;
        if(currentOrder){
            igtf_amount= currentOrder.igtf_amount   
        }
        else{
            igtf_amount = 0.0;
        }
        if (!paymentline) {
            var due = this.get_total_with_tax() - this.get_total_paid() - igtf_amount + this.get_rounding_applied();
        }
        else {
            var due = this.get_total_with_tax() - igtf_amount;
            var lines = this.paymentlines.models;
            for (var i = 0; i < lines.length; i++) {
                if (lines[i] === paymentline) {
                    break;
                } else {
                    due -= lines[i].get_amount();
                }
            }
        }
        return round_pr(due, this.pos.currency.rounding);
    },

});