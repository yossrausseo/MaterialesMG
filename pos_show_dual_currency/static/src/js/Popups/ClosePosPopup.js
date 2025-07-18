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
    setup() {
        super.setup();
        this.manualInputCashCountUSD = false;
        this.state = useState(this.getInitialState());
    },

    getInitialState() {

        const initialState = { notes: "", payments: {}, payments_usd: {} };
        if (this.pos.config.cash_control) {

            // Se asegura de que default_cash_details y su ID existan antes de usarlos.
            if (this.props.default_cash_details && this.props.default_cash_details.id) {
                initialState.payments[this.props.default_cash_details.id] = {
                    counted: "0",
                };
            }
            if (this.props.default_cash_details.default_cash_details_ref && this.props.default_cash_details.default_cash_details_ref.id) {
                initialState.payments_usd[this.props.default_cash_details.default_cash_details_ref.id] = {
                    counted: "0",
                };
            }
        }

        this.props.other_payment_methods.forEach((pm) => {
            // Se elimina el filtro `if (pm.type === "bank")` y se añade una guarda.
            if (pm && pm.id) {
                initialState.payments[pm.id] = {
                    counted: this.env.utils.formatCurrency(pm.amount, false),
                };
            }
        });

        return initialState;
    },

    getDifference(paymentId) {
        // Guarda de seguridad: si el ID es nulo/undefined o no existe en el estado,
        // la diferencia es 0.
        if (!paymentId || !this.state.payments[paymentId]) {
            return 0;
        }
        // Si todo es seguro, se llama a la función original.
        return super.getDifference(...arguments);
    },

    getDifferenceUSD(paymentId) {
        const counted = this.state.payments_usd[paymentId].counted;
        const expectedAmount =
            paymentId === this.props.default_cash_details?.default_cash_details_ref.id
                ? this.props.default_cash_details.default_cash_details_ref.amount
                : this.props.other_payment_methods.find((pm) => pm.id === paymentId).amount;

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
                if (this.state.openingCash && this.state.notes) {
                    this.state.notes += moneyDetailsNotes;
                } else {
                    this.state.notes = moneyDetailsNotes;
                }
            }
            this.moneyDetailsRef = moneyDetailsRef;
        }
    },

    //@override
    async confirm() {
        if (!this.cashControl || !this.hasDifferenceUSD()) {
            super.confirm();
        } else if (this.hasUserAuthorityUSD()) {
            const { confirmed } = await this.showPopup('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _t('Do you want to accept currency ref payments difference and post a profit/loss journal entry?'),
            });
            if (confirmed) {
                super.confirm();
            }
        } else {
            await this.showPopup('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _.str.sprintf(
                    _t('The maximum difference by currency ref allowed is %s.\n\
                            Please contact your manager to accept the closing difference.'),
                    this.pos.format_currency_ref(this.amountAuthorizedDiffUSD)
                ),
                confirmText: _t('OK'),
            })
        }
    },
    async closeSession() {
        this.customerDisplay?.update({ closeUI: true });
        // If there are orders in the db left unsynced, we try to sync.
        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }
        if (this.pos.config.cash_control) {
            const response = await this.orm.call(
                "pos.session",
                "post_closing_cash_details_ref",
                [this.pos.pos_session.id],
                {
                    counted_cash: parseFloat(
                        //this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].counted
                        String(this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].counted)
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
            // We have to handle the error manually otherwise the validation check stops the script.
            // In case of "rescue session", we want to display the next popup with "handleClosingError".
            // FIXME
            if (!error.data && error.data.message !== "This session is already closed.") {
                throw error;
            }
        }

        super.closeSession();
    },

})