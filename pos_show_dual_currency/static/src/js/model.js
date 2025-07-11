/** @odoo-module */
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
patch(PosStore.prototype, {
    //@override
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.res_currency_ref = loadedData['res_currency_ref'];
    },

    format_currency_ref(amount) {
        if (this.res_currency_ref.position === 'after') {
            return this.env.utils.formatCurrency(amount, false) + ' ' + (this.res_currency_ref.symbol || '');
        } else {
            return (this.res_currency_ref.symbol || '') + ' ' + this.env.utils.formatCurrency(amount, false);
        }
    },


});