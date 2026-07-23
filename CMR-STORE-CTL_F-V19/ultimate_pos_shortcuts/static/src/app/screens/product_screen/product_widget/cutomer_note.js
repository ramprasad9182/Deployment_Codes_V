/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { TextAreaPopup } from "@point_of_sale/app/utils/input_popups/textarea_popup";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();

        const pos = usePos();
        const popup = useService("popup");

        const handleKeyPress = (e) => {
            if (!(e instanceof KeyboardEvent)) return;

            // Check for Ctrl+6
            if (e.ctrlKey && e.key === '6') {
                e.preventDefault();
                e.stopPropagation();

                const selectedOrderline = pos.get_order()?.get_selected_orderline();

                if (!selectedOrderline) {
                    return;
                }
                if (Object.keys(this.popup.popups).length === 0) {
                    popup.add(TextAreaPopup, {
                        startingValue: selectedOrderline.get_customer_note(),
                        title: _t("Add Customer Note"),
                    }).then(result => {

                            if (result.confirmed) {
                                selectedOrderline.set_customer_note(result.payload);
                            }

                    });
                }
            }

        };

        window.addEventListener('keydown', handleKeyPress, { capture: true });

        // Clean up on destroy
        this.__customerNoteCleanup = () => {
            window.removeEventListener('keydown', handleKeyPress, { capture: true });
        };
    },

    destroy() {
        if (this.__customerNoteCleanup) {
            this.__customerNoteCleanup();
        }
        this._super();
    }
});