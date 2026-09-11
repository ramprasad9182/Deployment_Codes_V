/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class OrderSummaryPopup extends Component {
    static template = "nhcl_pos_sale.OrderSummaryPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");

        this.state = useState({
            showSummary: false,
        });
    }

    toggleSummary() {
        this.state.showSummary = !this.state.showSummary;
    }

    get summary() {
        const order = this.pos.get_order();

        // Default structure fallback to prevent template crash if no order is loaded
        const summaryData = {
            gross: "0.00",
            discount: "0.00",
            netSale: "0.00",
            credit_note_amount: "0.00",
            global_discount: "0.00",
            coupon_discount: "0.00",
            loyalty_reward_discount_value: "0.00",
            round_off: "0.00",
        };

        if (!order) {
            return summaryData;
        }

        const orderlines = order.get_orderlines() || [];

        let old_gross = 0;
        let gross = 0;
        let discount = 0;
        let line_discount = 0;
        let amount_discount = 0;
        let reward_discount = 0;
        let coupon_discount = 0;
        let loyalty_reward_discount_value = 0;
        let gdiscount_amount = 0.00;

        orderlines.forEach(line => {
            const price = Number(line.get_unit_price()) || 0;
            const qty = Number(line.quantity || line.qty) || 0;
            const line_total = price * qty;
            const line_discount_percent = Number(line.discount) || 0;

            if (line.gdiscount_amount) {
                gdiscount_amount += line.gdiscount_amount;
            }

            if (line.is_reward_line) {
                // 🧠 Separate Gift Card from other reward discounts
                if (line.product?.display_name === "Gift Card") {
                    coupon_discount += Math.abs(line_total);  // Only to coupon
                } else {
                    reward_discount += Math.abs(line_total); // Other reward discounts
                }
                return;
            }

            if (!line.is_fix_discount_line) {
                var lot_price = price;
                if (line.pack_lot_lines) {
                    const packLotLines = line.pack_lot_lines;
                    let k;
                    packLotLines.forEach((pack) => {k = pack.lot_name;});
                    const stockLot = line.pos.stock_lots_by_name[k];
                    if (stockLot && stockLot.stockLot.rs_price > 0) {
                        lot_price = stockLot.stockLot.rs_price;
                    }
                }
                gross += (lot_price * qty);
                old_gross += line_total;
            } else {
                amount_discount += -line_total;
            }

            if (line.reward_id || line.is_reward_line || line.discount_reward) {
                discount += line_total * (line_discount_percent / 100);
            } else {
                line_discount += line_total * (line_discount_percent / 100);
            }

            if (line.discount_value) {
                loyalty_reward_discount_value += line.discount_value;
            }
        });

        // Total real discount (excluding Gift Card)
        discount += reward_discount;

        // const global_discount_percent = Number(orderlines[0]?.gdiscount) || 0;
        const subtotal = old_gross - discount- coupon_discount;
        // const global_discount = subtotal * (global_discount_percent / 100) + line_discount + amount_discount;
        // const global_discount = old_gross * (global_discount_percent / 100) + line_discount + amount_discount;
        const global_discount = gdiscount_amount + line_discount + amount_discount;

        // Fallback computation for rounding & custom totals
        const customTotal = typeof order.get_custom_totalwithtax === 'function' ? order.get_custom_totalwithtax() : order.get_total_with_tax();
        const round_off = (parseFloat(customTotal.toFixed()) - customTotal).toFixed(2);
        // const netSale = subtotal - global_discount;
        const netSale = (subtotal - global_discount) + parseFloat(round_off);

        // Assign computed metrics formatted to 2 decimals
        summaryData.gross = gross.toFixed(2);
        // this.summary.gross = order.get_total_with_tax().toFixed(2);
        // this.summary.gross = order.get_custom_totalwithtax().toFixed(2);
        // this.summary.round_off = order.get_rounding_applied().toFixed(2);
        summaryData.round_off = round_off;
        summaryData.discount = discount.toFixed(2);
        summaryData.global_discount = global_discount.toFixed(2);
        // summaryData.netSale = netSale.toFixed(2);
        summaryData.netSale = netSale.toFixed();
        summaryData.coupon_discount = coupon_discount.toFixed(2);
        summaryData.credit_note_amount = (order.credit_note_amount || 0).toFixed(2);
        summaryData.loyalty_reward_discount_value = loyalty_reward_discount_value.toFixed(2);

        return summaryData;
    }
}
