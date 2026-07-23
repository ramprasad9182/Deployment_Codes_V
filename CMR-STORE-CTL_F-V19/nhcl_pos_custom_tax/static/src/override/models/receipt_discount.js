/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);

        const grossSale = this.get_orderlines().reduce((total, line) => {
            return total + (line.get_unit_price() * line.get_quantity());
        }, 0);

        result.gross_sale = grossSale;
        result.net_sale = result.total_with_tax || this.get_total_with_tax();

        console.log("=== RECEIPT DATA ===");
        console.log(result);
        console.log("gross_sale =", result.gross_sale);
        console.log("net_sale =", result.net_sale);
        // REAL ORDERLINES
        const lines = this.get_orderlines();
        // M DISCOUNT
        result.m_discount = lines
            .filter(line => line.is_fix_discount_line)
            .reduce(
                (sum, line) => sum + Math.abs(Number(line.price || 0)),
                0
            );
        // P DISCOUNT
        result.p_discount = lines
            .filter(line => line.is_reward_line && !line.is_fix_discount_line)
            .reduce(
                (sum, line) =>
                    sum + Math.abs(line.get_display_price()),
                0
            );
        const paymentLines = this.get_paymentlines();
        result.paymentlines = paymentLines.map(line => ({
                name: line.name,
                amount: line.amount,
        }));

        console.log('===>paymentlines',result.paymentlines)


        // Add total discount to each receipt line
        for (const receiptLine of result.orderlines || []) {
            const lineObj = receiptLine.line_obj;

            if (lineObj) {
                const gDiscount = Number(
                    lineObj.get_gdiscount_amount_str?.() || 0
                );

                const discount = Number(
                    lineObj.get_discount_amount_str?.() || 0
                );

                receiptLine.total_discount = gDiscount + discount;
            }
        }

        return result;
    },

});