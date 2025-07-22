/** @odoo-module */
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { MoneyDetailsPopupUSD } from "@pos_show_dual_currency/js/MoneyDetailsPopup/MoneyDetailsPopup";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { ConnectionLostError } from "@web/core/network/rpc_service";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

ClosePosPopup.props.push('amount_authorized_diff_ref');

patch(ClosePosPopup.prototype, {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.manualInputCashCountUSD = false;
    },


    /**
     * @override
     */
    getInitialState() {
        // Llama a la función original de Odoo para obtener un estado base válido.
        const initialState = super.getInitialState();
        
        initialState.payments_usd = {};
        if (this.pos.config.cash_control && this.props.default_cash_details?.default_cash_details_ref?.id) {
            initialState.payments_usd[this.props.default_cash_details.default_cash_details_ref.id] = {
                counted: "0",
            };
        }
        
        this.props.other_payment_methods.forEach((pm) => {
            // Si no existe ya una entrada para este método de pago (porque no es 'bank')...
            if (!initialState.payments[pm.id]) {
                // ...la creamos nosotros.
                initialState.payments[pm.id] = {
                    counted: this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });

        return initialState;
    },

    /**
     * @override
     */
    async confirm() {
        if (this.cashControl && this.hasDifferenceUSD() && !this.hasUserAuthorityUSD()) {
            await this.popup.add('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _.str.sprintf(
                    _t('The maximum difference by currency ref allowed is %s.\nPlease contact your manager to accept the closing difference.'),
                    this.pos.format_currency_ref(this.props.amount_authorized_diff_ref)
                ),
                confirmText: _t('OK'),
            });
            return;
        }

        if (this.cashControl && this.hasDifferenceUSD() && this.hasUserAuthorityUSD()) {
            const { confirmed } = await this.popup.add('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _t('Do you want to accept currency ref payments difference and post a profit/loss journal entry?'),
            });
            if (!confirmed) {
                return;
            }
        }
        
        return super.confirm(...arguments);
    },

    /**
     * @override
     */
    async closeSession() {
        if (this.pos.config.cash_control) {
            const response = await this.orm.call(
                "pos.session",
                "post_closing_cash_details_ref",
                [this.pos.pos_session.id],
                {
                    counted_cash: parseFloat(
                        String(this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id]?.counted || "0")
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
            if (!error.data?.message?.includes("already closed")) {
                throw error;
            }
        }

        return super.closeSession(...arguments);
    },

    // Este método es nuevo y es clave para las validaciones
    hasDifferenceUSD() {
        if (!this.pos.config.cash_control || !this.props.default_cash_details?.default_cash_details_ref?.id) {
            return false;
        }
        const diff = this.getDifferenceUSD(this.props.default_cash_details.default_cash_details_ref.id);
        return !this.env.utils.floatIsZero(diff);
    },

    // Este método es nuevo y es clave para las validaciones
    hasUserAuthorityUSD() {
        const diff = this.getDifferenceUSD(this.props.default_cash_details.default_cash_details_ref.id);
        return (
            this.props.is_manager ||
            this.props.amount_authorized_diff_ref == null ||
            Math.abs(diff) <= this.props.amount_authorized_diff_ref
        );
    },


    getDifference(paymentId) {
        if (!paymentId || !this.state.payments[paymentId]) {
            return 0;
        }
        return super.getDifference(...arguments);
    },

    getDifferenceUSD(paymentId) {
        if (!this.state.payments_usd[paymentId]) {
            return 0;
        }
        const counted = parseFloat(this.state.payments_usd[paymentId].counted || "0");
        const expectedAmount = this.props.default_cash_details.default_cash_details_ref.amount;
        return counted - expectedAmount;
    },

    async openDetailsPopupUSD() {
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        const { confirmed, payload } = await this.popup.add(MoneyDetailsPopupUSD, {
            moneyDetailsRef: this.moneyDetailsRef,
            action: action,
        });
        if (confirmed) {
            const { total, moneyDetailsRef, moneyDetailsNotes } = payload;
            this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].counted = total;
            if (moneyDetailsNotes) {
                this.state.notes = (this.state.notes ? this.state.notes + "\n" : "") + moneyDetailsNotes;
            }
            this.moneyDetailsRef = moneyDetailsRef;
        }
    },

})