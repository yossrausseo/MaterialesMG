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
     * La mejor práctica es llamar a super.setup() y LUEGO añadir tu lógica.
     * No es necesario volver a inicializar el estado aquí si lo hacemos bien en getInitialState.
     */
    setup() {
        super.setup();
        this.manualInputCashCountUSD = false;
        // El estado ya se inicializa correctamente dentro del `super.setup()` gracias al siguiente método.
    },


    /**
     * @override
     * ESTA ES LA CORRECCIÓN MÁS IMPORTANTE.
     * 1. Llamamos al `getInitialState` original para que Odoo construya el estado base.
     * 2. SOBRE ESE ESTADO, añadimos nuestra nueva propiedad `payments_usd`.
     * De esta forma, `state.payments` siempre estará completo y correcto.
     */
    getInitialState() {
        // Llama a la función original de Odoo para obtener un estado base válido.
        const initialState = super.getInitialState();
        
        // Ahora, añade tus propiedades personalizadas al estado que ya creó Odoo.
        initialState.payments_usd = {};
        if (this.pos.config.cash_control) {
            // Guarda para asegurar que los objetos existen antes de acceder a sus propiedades.
            if (this.props.default_cash_details?.default_cash_details_ref?.id) {
                initialState.payments_usd[this.props.default_cash_details.default_cash_details_ref.id] = {
                    counted: "0",
                };
            }
        }
        
        return initialState;
    },

    /**
     * @override
     * Reemplazamos la lógica de `confirm` por una que se integra mejor.
     * Realizamos nuestras validaciones de la moneda de referencia PRIMERO,
     * y si todo está bien, simplemente delegamos el control a la función `confirm` original.
     */
    async confirm() {
        // Valida si hay diferencias en la moneda de referencia (USD).
        if (this.cashControl && this.hasDifferenceUSD() && !this.hasUserAuthorityUSD()) {
            // Si hay una diferencia no autorizada, muestra el popup de error y detiene el proceso.
            await this.popup.add('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _.str.sprintf(
                    _t('The maximum difference by currency ref allowed is %s.\nPlease contact your manager to accept the closing difference.'),
                    this.pos.format_currency_ref(this.props.amount_authorized_diff_ref)
                ),
                confirmText: _t('OK'),
            });
            return; // Detiene la ejecución aquí.
        }

        if (this.cashControl && this.hasDifferenceUSD() && this.hasUserAuthorityUSD()) {
            // Si hay una diferencia autorizada, pregunta al usuario si desea continuar.
            const { confirmed } = await this.popup.add('ConfirmPopup', {
                title: _t('Currency Ref Payments Difference'),
                body: _t('Do you want to accept currency ref payments difference and post a profit/loss journal entry?'),
            });
            if (!confirmed) {
                return; // Si el usuario cancela, detiene el proceso.
            }
        }
        
        // Si no hay problemas con la moneda de referencia (o el usuario los aceptó),
        // deja que la función original de Odoo maneje el resto del proceso.
        // Esto ejecutará las validaciones de la moneda principal y el cierre normal.
        return super.confirm(...arguments);
    },

    /**
     * @override
     * Hacemos lo mismo para `closeSession`: llamamos a nuestros métodos ORM primero,
     * y luego dejamos que el `super` original haga su trabajo.
     */
    async closeSession() {
        // 1. Ejecuta tu lógica personalizada de la moneda de referencia
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

        // 2. Llama a la función original para que ejecute el cierre estándar.
        // Esta llamada ya no fallará porque `getInitialState` preparó el estado correctamente.
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


    getDifferenceUSD(paymentId) {
        // Añadimos una guarda de seguridad por si algo falla.
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
                // Tu lógica original tenía un bug aquí. Lo simplifico.
                this.state.notes = (this.state.notes ? this.state.notes + "\n" : "") + moneyDetailsNotes;
            }
            this.moneyDetailsRef = moneyDetailsRef;
        }
    },

})