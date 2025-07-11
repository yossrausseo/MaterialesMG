/** @odoo-module */
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { ConnectionLostError } from "@web/core/network/rpc_service";

// Añadir las nuevas propiedades al componente
ClosePosPopup.props = [
    ...ClosePosPopup.props,
    'default_cash_details_ref',
    'amount_authorized_diff_ref'
];

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.manualInputCashCountUSD = false;
        this.state = useState(this.getInitialState());
    },

    getInitialState() {
        const initialState = { 
            notes: "", 
            payments: {}, 
            cashDetailsRef: {
                counted: "0",
                moneyDetailsRef: {}  // Almacenará el desglose de billetes
            }
        };
        
        if (this.pos.config.cash_control) {
            if (this.props.default_cash_details) {
                initialState.payments[this.props.default_cash_details.id] = {
                    counted: "0",
                };
            }
            
            if (this.props.default_cash_details_ref) {
                initialState.cashDetailsRef = {
                    ...this.props.default_cash_details_ref,
                    counted: this.props.default_cash_details_ref.amount.toString()
                };
            }
        }

        this.props.other_payment_methods.forEach((pm) => {
            initialState.payments[pm.id] = {
                counted: this.env.utils.formatCurrency(pm.amount, false),
            };
        });

        return initialState;
    },

    // IMPLEMENTAR MÉTODO FALTANTE
    _getExpectedAmount(paymentId) {
        if (paymentId === this.props.default_cash_details?.id) {
            return this.props.default_cash_details.amount;
        } else {
            const pm = this.props.other_payment_methods.find(pm => pm.id === paymentId);
            return pm ? pm.amount : 0;
        }
    },

    getDifference(paymentId) {
        if (!this.state.payments || 
            !this.state.payments[paymentId] || 
            !this.state.payments[paymentId].counted) {
            return 0;
        }
        
        const counted = parseFloat(this.state.payments[paymentId].counted || "0");
        const expectedAmount = this._getExpectedAmount(paymentId);
        return counted - expectedAmount;
    },

    getDifferenceUSD() {
        if (!this.props.default_cash_details_ref || 
            !this.state.cashDetailsRef || 
            !this.state.cashDetailsRef.counted) {
            return 0;
        }
        
        const counted = parseFloat(this.state.cashDetailsRef.counted || "0");
        const expectedAmount = this.props.default_cash_details_ref.amount;
        return counted - expectedAmount;
    },

    async openDetailsPopupUSD() {
        const action = _t("Cash control - USD");
        this.pos.hardwareProxy?.openCashbox(action);
        
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopupUSD, {
            title: _t("USD Cash Details"),
            moneyDetailsRef: this.state.cashDetailsRef.moneyDetailsRef,
            action: action,
            currencyRefSymbol: this.currency_ref.symbol // Pasar el símbolo
        });
        
        if (confirmed) {
            // Actualizar estado con los nuevos valores
            this.state.cashDetailsRef.counted = payload.total;
            this.state.cashDetailsRef.moneyDetailsRef = payload.moneyDetailsRef;
            
            if (payload.moneyDetailsNotes) {
                this.state.notes = payload.moneyDetailsNotes;
            }
        }
    },
    
    hasDifferenceUSD() {
        if (!this.props.default_cash_details_ref) return false;
        return !this.env.utils.floatIsZero(
            this.getDifferenceUSD(),
            this.pos.currency_ref.decimal_places
        );
    },
    
    amountAuthorizedDiffUSD() {
        return this.props.amount_authorized_diff_ref || 0;
    },
    
    hasUserAuthorityUSD() {
        return Math.abs(this.getDifferenceUSD()) <= this.amountAuthorizedDiffUSD();
    },

    async closeSession() {
        this.customerDisplay?.update({ closeUI: true });
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }
        
        if (this.pos.config.cash_control && this.props.default_cash_details_ref) {
            const response = await this.orm.call(
                "pos.session",
                "post_closing_cash_details_ref",
                [this.pos.pos_session.id],
                {
                    counted_cash: parseFloat(
                        String(this.state.cashDetailsRef.counted)
                    ),
                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session_ref", [
                this.pos.pos_session.id,
                this.state.notes,
            ]);
        } catch (error) {
            if (!error.data || error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        super.closeSession();
    }
});