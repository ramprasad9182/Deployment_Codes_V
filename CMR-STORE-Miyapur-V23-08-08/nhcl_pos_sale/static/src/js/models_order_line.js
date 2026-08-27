/** @odoo-module */
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { parseFloat as oParseFloat } from "@web/views/fields/parsers";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
    },
    set_discount(discount) {
        var order = this.pos.get_order();
        if (order) {
            const orders = this.pos.get_order();
            // const lines = orders.get_orderlines()
            // const product = this.pos.db.get_product_by_id(this.pos.config.discount_product_id[0]);
//            const global_discount_product = lines.filter((line) => line.get_product() === product)
//            if (global_discount_product.length>0 && (discount !="" && discount !="remove")) {
//                            this.pos.popup.add(ErrorPopup, {
//                                'title': _t("Discount"),
//                                'body': _t("Global Discount has been Applied.For Item Discount ,Please Reset The Discount and Proceed!"),
//                            });
//                            return false
//                            }
//            else{
                var parsed_discount =
                typeof discount === "number"
                    ? discount
                    : isNaN(parseFloat(discount))
                    ? 0
                    : oParseFloat("" + discount);
                var disc = Math.min(Math.max(parsed_discount || 0, 0), 100);
                this.discount = disc;
                this.discountStr = "" + disc;
//            }
        }

    },

    //    Pranav Start
    onClickSelectLine(from_shortcutkey=false) {
        if (this.select_order_line) {
            this.select_order_line = false;
        } else {
            const orderlines = this.order.get_orderlines();
            // const has_fixed_discount_line = orderlines.some(line => line.is_fix_discount_line || line.get_gdiscount());
            // const not_allow_to_select_line = (this.discount_reward &&
            //         (this.get_discount() || this.get_gdiscount() || this.is_fix_discount_line));

            let reward_lines = orderlines.filter((l) => l.reward_product_id);
            let is_reward_line = false
            if (reward_lines.length > 0) {
                is_reward_line = reward_lines.some(line => line.reward_product_id === this.product.id);
            }

            if (this.reward_id) {
                const reward = this.pos.reward_by_id[this.reward_id];
                if (reward && reward.reward_type === "discount_on_product") {
                    if (!from_shortcutkey) {
                        this.pos.popup.add(ErrorPopup, {
                            'title': _t("Discount on Reward"),
                            'body': _t("Line Discount is not allowed on this Reward!"),
                        });
                    }
                    return;
                }
            }

            // if ((this.reward_id && is_reward_line) || is_reward_line || has_fixed_discount_line || not_allow_to_select_line) {
            //     if (!from_shortcutkey) {
            //         this.pos.popup.add(ErrorPopup, {
            //             'title': _t("Invalid Line Selection"),
            //             'body': _t("This line cannot be selected for a discount!"),
            //         });
            //     }
            //     return;
            // }
            this.select_order_line = true;
//            if (this.get_discount() || this.get_gdiscount() || this.fix_discount) {
//                this.pos.popup.add(ErrorPopup, {
//                    'title': _t("Invalid Line Selection"),
//                    'body': _t("This line cannot be selected for a discount!"),
//                });
//            } else {
//                this.select_order_line = true;
//            }
        }
    },
//    STOP
});