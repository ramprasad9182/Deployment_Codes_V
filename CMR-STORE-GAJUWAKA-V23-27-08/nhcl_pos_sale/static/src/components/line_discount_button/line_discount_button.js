/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { parseFloat } from "@web/views/fields/parsers";

export class LineDiscountButton extends Component {
    static template = "nhcl_pos_sale.LineDiscountButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async click() {
        var self = this;
        const order = this.pos.get_order();
        if (!order) return;

        const grossTotal = typeof order.get_custom_totalwithtax === 'function' 
            ? order.get_custom_totalwithtax() 
            : order.get_total_with_tax();

        let creditNoteAmt = order.credit_note_amount || 0;
        if (order.paymentlines) {
            for (const line of order.paymentlines) {
                if (line.payment_method && line.payment_method.is_credit_settlement) {
                    creditNoteAmt = Math.max(creditNoteAmt, line.amount || 0);
                }
            }
        }

        const netCartValue = grossTotal - creditNoteAmt;
        if (netCartValue <= 0) {
            this.popup.add(ErrorPopup, {
                title: _t("Discount Error"),
                body: _t("Discount is not allowed when total cart value is 0 or less."),
            });
            return;
        }

        const orderlines = order.get_orderlines();
        const lines = orderlines.filter(line => line.select_order_line);
        const has_fixed_discount_line = orderlines.some(line => line.is_fix_discount_line || line.get_gdiscount());
        if (has_fixed_discount_line) {
            this.popup.add(ErrorPopup, {
                title: _t("Discount Error"),
                body: _t("Global/Amount Discount is already applied!"),
            });
            return;
        }
        if (lines.length < 1) {
            this.popup.add(ErrorPopup, {
                title: _t("Discount"),
                body: _t("Lines are not selected, please select lines!"),
            });
        } else {
            const { confirmed, payload } = await this.popup.add(NumberPopup, {
                title: _t("Discount Percentage"),
                startingValue: this.pos.config.discount_pc,
                isInputSelected: true,
            });
            if (confirmed) {
                const parsedVal = parseFloat(payload);
                if (isNaN(parsedVal) || parsedVal < 0) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Discount Error"),
                        body: _t("Negative discount amount/percentage is not allowed!"),
                    });
                    return;
                }
                const val = Math.max(0, Math.min(100, parsedVal));
                const cashier = this.pos.get_cashier();
                if (cashier && cashier.max_selected_lines_discount > 0 && val > cashier.max_selected_lines_discount) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Discount Error"),
                        body: _t(`You cannot give selected lines discount more than ${cashier.max_selected_lines_discount}%.`),
                    });
                    return;
                }
                await self.apply_discount(val);
            }
        }
    }

    async apply_discount(pc) {
        const order = this.pos.get_order();
        const lines = order.get_orderlines().filter(line => line.select_order_line);

        const has_fixed_discount_line = lines.some(line => line.is_fix_discount_line || line.get_gdiscount());

        if (!has_fixed_discount_line) {
            for (const line of lines) {
                const is_reward_line = lines.some(l => l.reward_product_id === line.product.id)
                if (!(line.reward_id || line.discount_reward || is_reward_line)) {
                    line.set_discount(pc);
                    const qty = line.get_quantity();
                    // const prices = line.get_all_prices(qty);
                }
                line.select_order_line = false;
            }
            order._updateRewards();
        }
    }

}

ProductScreen.addControlButton({
    component: LineDiscountButton,
    condition: function () {
        const { module_pos_discount, discount_product_id } = this.pos.config;
        return module_pos_discount && discount_product_id;
    },
});
