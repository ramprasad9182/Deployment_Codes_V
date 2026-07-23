/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

import { CustomButtonPopup } from "@nhcl_pos_sale/app/custom_popup/custom_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

let salesShortcutHandler = null;

patch(ProductScreen.prototype, {

    setup() {
        super.setup();

        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");

        this.__isDestroyed = false;
        this._salesPopupOpen = false;

        const addSalesPerson = async () => {

            if (this._salesPopupOpen) {
                return;
            }

            this._salesPopupOpen = true;

            try {

                const order = this.pos.get_order();
                const selectedOrderline = order?.get_selected_orderline();

                if (!selectedOrderline) {

                    await this.popup.add(ErrorPopup, {
                        title: _t("No Order Line"),
                        body: _t("Please select a product first."),
                    });

                    return;
                }

                const { confirmed, payload } = await this.popup.add(
                    CustomButtonPopup,
                    {
                        startingValue: "",
                        title: _t("Add Sales Person"),
                    }
                );

                if (!confirmed) return;

                const value = (payload || "").trim();

                if (!value) {

                    await this.popup.add(ErrorPopup, {
                        title: _t("Sales employee mandatory"),
                        body: _t("Please Enter Sales Person Id."),
                    });

                    return;
                }

                let employees;

                try {

                    employees = await this.orm.call(
                        "hr.employee",
                        "search_read",
                        [[["barcode", "=", value]]],
                        {
                            fields: ["id", "name", "barcode"],
                            limit: 1,
                        }
                    );

                } catch (error) {
                    // Ignore server error popup
                    console.warn("Server connection ignored:", error);
                    return;
                }

                const employee = employees?.[0];

                if (!employee) {

                    await this.popup.add(ErrorPopup, {
                        title: _t("Invalid Employee"),
                        body: _t("Please Enter Correct Employee Id."),
                    });

                    return;
                }

                const multiLines = order.get_orderlines().filter(
                    (line) => line.select_order_line
                );

                let targetLines = [];

                if (multiLines.length > 0) {
                    targetLines = multiLines;
                } else {
                    const currentLine = order.get_selected_orderline();
                    if (currentLine) {
                        targetLines = [currentLine];
                    }
                }

                if (!targetLines.length) return;

                for (const line of targetLines) {

                    line.set_emp_no(employee.name);
                    line.set_badge_id(employee.barcode);
                    line.set_employee_id(employee.id);

                    // reset multi-selection
                    line.select_order_line = false;
                }
                order._updateRewards();
            } finally {

                this._salesPopupOpen = false;

            }
        };

        const handleKeyPress = (e) => {

            if (this.__isDestroyed) return;
            if (!(e instanceof KeyboardEvent)) return;

            if (e.ctrlKey && e.key === "3") {

                e.preventDefault();
                e.stopPropagation();

                addSalesPerson();
            }
        };

        // IMPORTANT FIX: remove old listener before adding new one
        if (salesShortcutHandler) {
            window.removeEventListener("keydown", salesShortcutHandler, { capture: true });
        }

        salesShortcutHandler = handleKeyPress;

        window.addEventListener("keydown", salesShortcutHandler, { capture: true });
    },

    destroy() {

        this.__isDestroyed = true;

        if (salesShortcutHandler) {
            window.removeEventListener("keydown", salesShortcutHandler, { capture: true });
            salesShortcutHandler = null;
        }

        super.destroy();
    },

});