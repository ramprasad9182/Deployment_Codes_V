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
        let has_gdiscount_lines = orderlines.some(line => line.get_gdiscount());
        let has_line_discount = false
        if (!has_gdiscount_lines) {
            has_line_discount = orderlines.some(line => !line.discount_reward && line.get_discount());
        }
        if (has_gdiscount_lines || has_line_discount) {
            this.pos.popup.add(ErrorPopup, {
                'title': _t("Amount Discount Error"),
                'body': _t("Discount is already applied to the cart!"),
            });
            return;
        }

        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: _t("Amount Discount"),
            startingValue: 0,
            isInputSelected: true,
        });
        if (confirmed) {
            const val = parseFloat(payload);
//            const val = parseFloat(
//                round_di(parseFloat(payload) / lines.length, 2).toFixed(2)
//            );

            let create_new_line = true;
//            lines.forEach(line => {
//                if (line.get_is_fix_discount_line()) {
////                    line.set_fix_discount(val);
//                    create_new_line = false
//                    line.set_unit_price(-payload);
//                    break;
//                }
//            });

            for (let line of orderlines) {
                if (line.get_is_fix_discount_line()) {
                    create_new_line = false;
                    line.set_unit_price(-val);
                    break;
                }
            }
            if (create_new_line) {
                const line_values = {
                    pos: this.pos,
                    order: order,
                    product: this.pos.db.get_product_by_id(this.pos.config.discount_product_id[0]),
                    description: _t("%s Amount Discount on order", val),
                    price: -val,
                    tax_ids: false,
                    price_manually_set: false,
                    price_type: "manual",
                    is_fix_discount_line: true,
                };
                const new_line = new Orderline({ env: this.env }, line_values);
                new_line.set_is_fix_discount_line(true);
                order.add_orderline(new_line);
            }
//            order.set_is_fix_discount_line(true);
            order._updateRewards();
        }

    }
}
ProductScreen.addControlButton({
    component: SetFixDiscountButton,
});