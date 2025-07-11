/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { floatIsZero } from "@web/core/utils/numbers";
import { NumericInput } from "@point_of_sale/app/generic_components/inputs/numeric_input/numeric_input";

export class MoneyDetailsPopupUSD extends AbstractAwaitablePopup {
    static template = "pos_show_dual_currency.MoneyDetailsPopupUSD";
    static components = { NumericInput };
    static props = {
        ...AbstractAwaitablePopup.props,
        currencyRefSymbol: { type: String, optional: true },
        moneyDetailsRef: { type: Object, optional: true },
        action: { type: String, optional: true }
    };

    setup() {
        super.setup();
        this.pos = usePos();
        
        // CORRECCIÓN: Obtener currency_ref del pos.session
        this.currency_ref = this.pos.pos_session.ref_me_currency_id || this.pos.res_currency_ref;
        
         // Inicializar con props o valores por defecto
        this.state = useState({
            moneyDetailsRef: this.props.moneyDetailsRef || 
                Object.fromEntries(this.pos.bills.map(bill => [bill.value, 0]))
        });
    }

    computeTotal(moneyDetailsUSD = this.state.moneyDetailsRef) {
        return Object.entries(moneyDetailsUSD).reduce((total, [value, inputQty]) => {
            const quantity = isNaN(inputQty) ? 0 : inputQty;
            return total + parseFloat(value) * quantity;
        }, 0);
    }

    async getPayload() {
        const total = this.computeTotal();
        let moneyDetailsNotes = '';
        
        // CORRECCIÓN: Usar decimales de la moneda de referencia
        if (!floatIsZero(total, this.currency_ref.decimal_places)) {
            moneyDetailsNotes = 'Ref Currency Money details: \n';
            
            this.pos.bills.forEach((bill) => {
                if (this.state.moneyDetailsRef[bill.value] > 0) {
                    moneyDetailsNotes += `  - ${this.state.moneyDetailsRef[bill.value]
                        } x ${this.pos.format_currency_ref(bill.value)}\n`;
                }
            });
        }
        
        return {
            total: total,
            moneyDetailsNotes: moneyDetailsNotes,
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
    
    // CORRECCIÓN: Función para analizar valores flotantes
    parseFloat(value) {
        return isNaN(parseFloat(value)) ? 0 : parseFloat(value);
    }
}