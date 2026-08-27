/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";

patch(DiscountButton.prototype, {
    async click() {
        const order = this.pos.get_order();
        const lines = order.get_orderlines();

//        const original_lines = lines.filter(line => !line.is_reward_line && !line.get_discount() && !line.fix_discount && !line.discount_reward);
//        const original_lines = lines.filter(line => !line.is_reward_line && !line.fix_discount && (!line.get_discount() || (line.get_discount() && line.discount_reward)));
//        if (original_lines.length < 1) {
//            return;
//        }

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
            this.pos.popup.add(ErrorPopup, {
                title: _t("Global Discount Error"),
                body: _t("Discount is not allowed when total cart value is 0 or less."),
            });
            return;
        }

        let allow_gdiscount = true;
        lines.forEach(line => {
            if (!line.discount_reward && (line.get_discount() || line.is_fix_discount_line)) {
                allow_gdiscount = false;
            };
        });
        if (!allow_gdiscount) {
            this.pos.popup.add(ErrorPopup, {
                'title': _t("Global Discount Error"),
                'body': _t("Discount is already applied to the cart!"),
            });
            return;
        }

        var self = this;
        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: _t("Discount Percentage"),
            startingValue: this.pos.config.discount_pc,
        });
        if (confirmed) {
            const parsedVal = parseFloat(payload);
            if (isNaN(parsedVal) || parsedVal < 0) {
                this.pos.popup.add(ErrorPopup, {
                    title: _t("Global Discount Error"),
                    body: _t("Negative discount amount/percentage is not allowed!"),
                });
                return;
            }
            const val = Math.round(
                Math.max(0, Math.min(100, parsedVal))
            );
            const cashier = this.pos.get_cashier();
            if (cashier && cashier.max_global_discount > 0 && val > cashier.max_global_discount) {
                this.pos.popup.add(ErrorPopup, {
                    title: _t("Global Discount Error"),
                    body: _t(`You cannot give global discount more than ${cashier.max_global_discount}%.`),
                });
                return;
            }
            await self.apply_discount(val);
        }
    },
    apply_discount(pc) {
        const order = this.pos.get_order();

        order.global_discount = pc;

        const lines = order.get_orderlines().filter(line => !line.is_reward_line && !line.is_fix_discount_line && (!line.get_discount() || (line.get_discount() && line.discount_reward)));
        let reward_lines = order.get_orderlines().filter((l) => l.reward_product_id);
        for (const line of lines) {
            let is_reward_line = false
            if (reward_lines.length > 0) {
                is_reward_line = reward_lines.some(l => l.reward_product_id === line.product.id)
            }

            if (line.reward_id) {
                const reward = this.pos.reward_by_id[line.reward_id];
                if (reward && reward.reward_type === "discount_on_product") {
                    continue
                }
            }

//            if ((line.reward_id && !is_reward_line) && !is_reward_line && !line.is_reward_line && !line.fix_discount && !line.is_fix_discount_line) {
            if ((line.reward_id && !is_reward_line) || (!is_reward_line && !line.is_reward_line && !line.fix_discount && !line.is_fix_discount_line)) {
                line.set_gdiscount(pc);
                const qty = line.get_quantity();
                const prices = line.get_all_prices(qty);
            }
        }

         order._updateRewards();
//         order._resetPrograms();
//         order._updateRewardLines();
    },
});
