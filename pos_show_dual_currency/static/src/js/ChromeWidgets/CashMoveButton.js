/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { CashMovePopupUSD } from "./CashMovePopupUSD";

patch(Navbar.prototype, {

    onCashMoveButtonClickUSD() {
        this.hardwareProxy.openCashbox(_t("Cash in / out"));
        this.popup.add(CashMovePopupUSD);
    }
});