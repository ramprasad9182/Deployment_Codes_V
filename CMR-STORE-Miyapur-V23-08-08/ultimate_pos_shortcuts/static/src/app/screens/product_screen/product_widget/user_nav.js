/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";



patch(SelectionPopup.prototype, {
    setup() {
        super.setup();
        debugger;
        this._handleEnterKey = (ev) => {
            if (ev.key !== "Enter") {
                return;
            }

            // Find first visible selectable item
            const firstItem = document.querySelector(
                ".selection-popup .selection-item, .popup .selection-item"
            );

            if (firstItem) {
                ev.preventDefault();
                ev.stopPropagation();
                firstItem.click();
            }
        };

        onMounted(() => {
            setTimeout(() => {
                const input =
                    this.el?.querySelector("input") ||
                    document.querySelector(".popup input");

                if (input) {
                    input.focus();
                    input.select();
                }
            }, 50);

            document.addEventListener("keydown", this._handleEnterKey, true);
        });

        onWillUnmount(() => {
            document.removeEventListener(
                "keydown",
                this._handleEnterKey,
                true
            );
        });
    },
});


patch(ProductScreen.prototype, {
    setup() {
        super.setup();

        const pos = usePos();
        const popup = useService("popup");

        const checkPin = async (employee) => {
            const { confirmed, payload: inputPin } = await popup.add(
                NumberPopup,
                {
                    isPassword: true,
                    title: _t("Password?"),
                }
            );

            if (!confirmed) {
                return false;
            }
            debugger;
            if (employee.pin !== Sha1.hash(inputPin)) {
                await popup.add(ErrorPopup, {
                    title: _t("Incorrect Password"),
                    body: _t("Please try again."),
                });
                return false;
            }

            return true;
        };

        const handleKeyPress = async (e) => {
            if (!(e instanceof KeyboardEvent)) {
                return;
            }

            if (e.key !== "F5") {
                return;
            }

            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            if (!pos.config.module_pos_hr) {
                return;
            }

            if (Object.keys(popup.popups).length !== 0) {
                return;
            }

            const employeesList = pos.employees
                .filter((employee) => employee.id !== pos.get_cashier()?.id)
                .map((employee) => ({
                    id: employee.id,
                    item: employee,
                    label: employee.name,
                    isSelected: false,
                }));

            if (!employeesList.length) {
                if (!pos.get_cashier()?.id) {
                    await popup.add(ErrorPopup, {
                        title: _t("No Cashiers"),
                        body: _t(
                            "There are no employees to select as cashier. Please create one."
                        ),
                    });
                }
                return;
            }

            const { confirmed, payload: employee } = await popup.add(
                SelectionPopup,
                {
                    title: _t("Change Cashier"),
                    list: employeesList,
                }
            );

            if (!confirmed || !employee) {
                return;
            }

            if (employee.pin && !(await checkPin(employee))) {
                return;
            }

            pos.set_cashier(employee);
        };

        window.addEventListener("keydown", handleKeyPress, {
            capture: true,
        });

        this.__cashierShortcutCleanup = () => {
            window.removeEventListener("keydown", handleKeyPress, {
                capture: true,
            });
        };
    },

    destroy() {
        if (this.__cashierShortcutCleanup) {
            this.__cashierShortcutCleanup();
        }
        super.destroy();
    },
});