/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { roundDecimals as round_di } from "@web/core/utils/numbers";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Orderline } from "@point_of_sale/app/store/models";

export class SetFixDiscountButton extends Component {
    static template = "wt_pos_fix_discount.SetFixDiscountButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }
    async click() {
        const order = this.pos.get_order();
        const orderlines = order.get_orderlines();
//        const original_lines = orderlines.filter(line => !line.is_reward_line && !line.get_discount());
        if (orderlines.length < 1) {
            return;
        }

//        let allow_fix_discount = true;
//        orderlines.forEach(line => {
//            if (!line.discount_reward && (line.get_gdiscount() || line.get_discount())) {
//                allow_fix_discount = false;
//            }
//        });
//        if (!allow_fix_discount) {
//            this.pos.popup.add(ErrorPopup, {
//                'title': _t("Amount Discount Error"),
//                'body': _t("Discount is already applied to the cart!"),
//            });
//            return;
//        }
        let has_line_discount = orderlines.some(line => !line.discount_reward && line.get_discount());
        if (has_line_discount) {
            this.pos.popup.add(ErrorPopup, {
                'title': _t("Amount Discount Error"),
                'body': _t("Discount is already applied to the cart!"),
            });
            return;
        }

        let current_discount_amount = 0;
        for (const line of orderlines) {
            current_discount_amount += line.get_gdiscount_amount() || 0;
        }

        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: _t("Amount Discount"),
            startingValue: current_discount_amount || 0,
            isInputSelected: true,
        });
        if (confirmed) {
            const val = parseFloat(payload);
            if (isNaN(val) || val < 0) {
                return;
            }

            // Remove any legacy fix discount lines if present in the cart
            for (let line of [...orderlines]) {
                if (line.get_is_fix_discount_line()) {
                    order._unlinkOrderline(line);
                }
            }

            // Re-fetch orderlines in case legacy lines were unlinked
            const current_lines = order.get_orderlines();

            // Identify eligible lines (same logic as DiscountButton)
            const lines = current_lines.filter(line => !line.is_reward_line && !line.is_fix_discount_line && (!line.get_discount() || (line.get_discount() && line.discount_reward)));
            let reward_lines = current_lines.filter((l) => l.reward_product_id);
            const eligible_lines = [];
            for (const line of lines) {
                let is_reward_line = false;
                if (reward_lines.length > 0) {
                    is_reward_line = reward_lines.some(l => l.reward_product_id === line.product.id);
                }

                if (line.reward_id) {
                    const reward = this.pos.reward_by_id[line.reward_id];
                    if (reward && reward.reward_type === "discount_on_product") {
                        continue;
                    }
                }

                if ((line.reward_id && !is_reward_line) || (!is_reward_line && !line.is_reward_line && !line.fix_discount && !line.is_fix_discount_line)) {
                    eligible_lines.push(line);
                }
            }

            if (eligible_lines.length === 0) {
                return;
            }

            // Calculate total eligible base price before global discount
            let total_eligible_amount = 0;
            // Temporarily store original gdiscounts and set to 0 to get original base price
            const original_gdiscounts = [];
            for (const line of eligible_lines) {
                original_gdiscounts.push(line.get_gdiscount() || 0);
                line.set_gdiscount(0);
            }

            for (const line of eligible_lines) {
                total_eligible_amount += line.get_display_price();
            }

            let pc = 0;
            if (val > 0 && total_eligible_amount > 0) {
                pc = Math.min(100, Math.max(0, (val / total_eligible_amount) * 100));
                // Round to 4 decimal places
                pc = parseFloat(pc.toFixed(4));
            }

            order.global_discount = pc;
            for (const line of eligible_lines) {
                line.set_gdiscount(pc);
                // trigger internal price recomputations
                const qty = line.get_quantity();
                line.get_all_prices(qty);
            }

            order._updateRewards();
        }

    }
}
ProductScreen.addControlButton({
    component: SetFixDiscountButton,
});