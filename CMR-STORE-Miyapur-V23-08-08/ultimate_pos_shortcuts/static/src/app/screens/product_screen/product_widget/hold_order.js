/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype,  {
    setup() {
        super.setup();

        const handleKeyPress = (e) => {
            if (!(e instanceof KeyboardEvent)) return;

            // Check for Ctrl+S
            if (e.ctrlKey && (e.key === '7')) {
                e.preventDefault();
                e.stopPropagation();

                // Find and click the save button
                const buttons = document.querySelectorAll('.control-button');
                for (let button of buttons) {
                    if (Object.keys(this.popup.popups).length === 0) {
                        if (button.textContent.includes('Hold') ||
                            button.querySelector('.fa-pause')) {
                            button.click();
                            continue
                        }
                    }
                }
            }
        };

        window.addEventListener('keydown', handleKeyPress);

        // Clean up
        this.__saveShortcutCleanup = () => {
            window.removeEventListener('keydown', handleKeyPress);
        };
    },

    destroy() {
        if (this.__saveShortcutCleanup) {
            this.__saveShortcutCleanup();
        }
        super.destroy();
    }
});