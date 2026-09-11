/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        this.select_all_current_order_lines = false;

        const handleKeyPress = (e) => {
            if (!(e instanceof KeyboardEvent)) return;

            // Check for Ctrl+5
            if (e.shiftKey && (e.key === 'd' || e.key === 'D')) {
                e.preventDefault();
                e.stopImmediatePropagation();
                e.stopPropagation();
                e.stopImmediatePropagation();

                // Look for button that contains discount text
                const buttons = document.querySelectorAll('.control-button');
                for (let button of buttons) {
                    if (Object.keys(this.popup.popups).length === 0) {
                        if (button.textContent.includes('Selected Lines Discount') ||
                            button.querySelector('.fa-scissors')) {
                            button.click();
                            continue;
                        }
                    }
                }
            }
            // For Select all current order cart lines
            if (e.shiftKey && (e.key === 'a' || e.key === 'A')) {
                e.preventDefault();
                this.onClickSelectAllCurrentOrderLines();
            }
        };

        window.addEventListener('keydown', handleKeyPress);

        // Clean up
        this.__discountShortcutCleanup = () => {
            window.removeEventListener('keydown', handleKeyPress);
        };
    },

    destroy() {
        if (this.__discountShortcutCleanup) {
            this.__discountShortcutCleanup();
        }
        super.destroy();
    },

    onClickSelectAllCurrentOrderLines() {
        const order = this.pos.get_order();
        if (!order) return;

        let select_order_in_ticket_screen = false
        if (this.select_all_current_order_lines) {
            this.select_all_current_order_lines = false;
            select_order_in_ticket_screen = false;
        } else {
            this.select_all_current_order_lines = true;
            select_order_in_ticket_screen = true;
        }

        const lines = order.get_orderlines();

        for (const line of lines) {
            if (line.select_order_line) {
                line.select_order_line = select_order_in_ticket_screen;
                // this.show_delete_button = select_order_in_ticket_screen;
            } else {
                line.select_order_line = select_order_in_ticket_screen;
                // this.show_delete_button = select_order_in_ticket_screen;
            }
        }
    },
});