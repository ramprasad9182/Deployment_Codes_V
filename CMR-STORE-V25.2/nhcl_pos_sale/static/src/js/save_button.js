/** @odoo-module **/

import { SaveButton } from "@point_of_sale/app/screens/product_screen/control_buttons/save_button/save_button";
import { patch } from "@web/core/utils/patch";

patch(SaveButton.prototype, {
    async onClick() {
        const order = this.pos.get_order();
        const payment_lines = order.get_paymentlines();

        if (payment_lines.length) {
            // Create a copy ([...lines]) so removing items doesn't break the loop
            for (const payment of [...payment_lines]) {
                if (!payment.amount) {
                    order.remove_paymentline(payment);
                }
            }
        }

        // Now that all zero-amount lines are gone, proceed to base logic
        await super.onClick(...arguments);
    }
});