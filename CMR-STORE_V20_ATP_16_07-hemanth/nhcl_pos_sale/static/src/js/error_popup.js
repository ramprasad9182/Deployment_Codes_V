/** @odoo-module **/

import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(ErrorPopup.prototype, {
    setup() {
        super.setup(...arguments);

        // Define the keyboard handler
        this._onKeyDown = (ev) => {
            // if (ev.key === "Escape" || ev.key === "Enter") {
            if (ev.key === "Enter") {
                this.confirm(); // Closes the popup
            }
        };

        // Attach listener when popup opens
        onMounted(() => {
            window.addEventListener("keydown", this._onKeyDown);
        });

        // Clean up when popup closes
        onWillUnmount(() => {
            window.removeEventListener("keydown", this._onKeyDown);
        });
    }
});
