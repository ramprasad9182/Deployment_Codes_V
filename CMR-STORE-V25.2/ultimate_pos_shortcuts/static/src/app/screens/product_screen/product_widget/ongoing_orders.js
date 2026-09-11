/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();

        const handleKeyPress = (e) => {
            if (!(e instanceof KeyboardEvent)) return;

            // Check for Ctrl+T
            if (Object.keys(this.popup.popups).length === 0) {
                if (e.ctrlKey && (e.key === '8')) {
                    e.preventDefault();
                    e.stopPropagation();

                    // Navigate to TicketScreen where saved orders are shown
                    this.pos.showScreen("TicketScreen");
                }
            }
        };

        window.addEventListener('keydown', handleKeyPress);

        // Clean up
        this.__ticketScreenShortcutCleanup = () => {
            window.removeEventListener('keydown', handleKeyPress);
        };
    },

    destroy() {
        if (this.__ticketScreenShortcutCleanup) {
            this.__ticketScreenShortcutCleanup();
        }
        super.destroy();
    }
});