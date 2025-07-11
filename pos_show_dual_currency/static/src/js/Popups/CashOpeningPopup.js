/** @odoo-module */

import { CashOpeningPopup } from "@point_of_sale/app/store/cash_opening_popup/cash_opening_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { MoneyDetailsPopupUSD } from "@pos_show_dual_currency/js/MoneyDetailsPopup/MoneyDetailsPopup";


patch(CashOpeningPopup.prototype, {
    setup() {
        super.setup();
        this.manualInputCashCountUSD = null;
        this.moneyDetailsRef = null;
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.state = useState({
            notes: "",
            openingCash: this.env.utils.formatCurrency(
                this.pos.pos_session.cash_register_balance_start || 0,
                false
            ) || 0,
            openingCashUSD: this.pos.pos_session.cash_register_balance_start_mn_ref || 0,
            displayMoneyDetailsPopupUSD: false,
        });
    },

    //@override
    async confirm() {
        this.pos.pos_session.cash_register_balance_start_mn_ref = this.state.openingCashUSD;
        if (!this.state.openingCashUSD) {
            this.state.openingCashUSD = 0;
        }
        this.orm.call("pos.session", "set_cashbox_pos_usd", [
            this.pos.pos_session.id, 
            parseFloat(this.state.openingCashUSD), 
            this.state.notes_ref
        ]);
        super.confirm();
    },

    async openDetailsPopupUSD() {
        this.state.openingCashUSD = 0;
        this.state.displayMoneyDetailsPopupUSD = true;
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopupUSD, {
            moneyDetailsRef: this.moneyDetailsRef,
            action: action,
        });
        if (confirmed) {
            const { total, moneyDetailsRef, moneyDetailsNotes } = payload;
            this.state.openingCashUSD = total;
            if (moneyDetailsNotes) {
                if (this.state.openingCash && this.state.notes){
                    this.state.notes += moneyDetailsNotes;
                }else {
                    this.state.notes = moneyDetailsNotes;
                }
            }
            this.moneyDetailsRef = moneyDetailsRef;
        }
    },

    handleInputChangeUSD() {
        this.manualInputCashCountUSD = true;
        if (typeof(parseInt(this.state.openingCashUSD)) !== "number") {
            this.state.openingCashUSD = 0;
        }
        this.state.notes_ref = "";
    }

});