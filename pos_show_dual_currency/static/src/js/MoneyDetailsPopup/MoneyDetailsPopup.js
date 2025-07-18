/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { floatIsZero } from "@web/core/utils/numbers";
import { NumericInput } from "@point_of_sale/app/generic_components/inputs/numeric_input/numeric_input";


export class MoneyDetailsPopupUSD extends AbstractAwaitablePopup {
    static template = "pos_show_dual_currency.MoneyDetailsPopupUSD";
    static components = { NumericInput };

    setup() {
        super.setup();
        this.pos = usePos();
        this.currency_ref = this.pos.res_currency_ref;
        this.state = useState({
            moneyDetailsRef: Object.fromEntries(this.pos.bills.map(bill => ([bill.value, 0]))),

        });
    }

    computeTotal(moneyDetailsUSD = this.state.moneyDetailsRef) {
        return Object.entries(moneyDetailsUSD).reduce((total, [value, inputQty]) => {
            const quantity = isNaN(inputQty) ? 0 : inputQty;
            return total + parseFloat(value) * quantity;
        }, 0);
    }

    //@override
    async getPayload() {
        let moneyDetailsNotes = !floatIsZero(this.computeTotal(), this.currency_ref.decimal_places)
            ? 'Ref Currency Money details: \n'
            : null;

        this.pos.bills.forEach((bill) => {
            if (this.state.moneyDetailsRef[bill.value]) {
                moneyDetailsNotes += `  - ${this.state.moneyDetailsRef[bill.value]
                    } x ${this.pos.format_currency_ref(bill.value)}\n`;
                    // } x ${this.env.utils.formatCurrency(bill.value)}\n`;     
            }
        });
        
        return {
            total: this.computeTotal(),
            moneyDetailsNotes,
            moneyDetailsRef: { ...this.state.moneyDetailsRef },
            action: this.props.action,
        };
    }

    async cancel() {
        super.cancel();
        if (
            this.pos.config.iface_cashdrawer &&
            this.pos.hardwareProxy.connectionInfo.status === "connected"
        ) {
            this.pos.logEmployeeMessage(this.props.action, "ACTION_CANCELLED");
        }
    }
    _parseFloat(value) {
        return parseFloat(value);
    }
}
