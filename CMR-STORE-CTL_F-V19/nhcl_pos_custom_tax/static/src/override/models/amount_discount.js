/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        // REAL ORDERLINES
        const lines = this.get_orderlines();
        result.badge = this.badge || '';
        result.product_total = this.get_custom_totalwithtax();
        // M DISCOUNT
        result.m_discount = lines
            .filter(line => line.is_fix_discount_line)
            .reduce(
                (sum, line) => sum + Math.abs(Number(line.price || 0)),
                0
            );
        // P DISCOUNT
        result.p_discount = lines
            .filter(line =>
                line.is_reward_line &&
                !line.is_fix_discount_line
            )
            .reduce(
                (sum, line) => sum + Math.abs(Number(line.price || 0)),
                0
            );
        return result;
    },

});