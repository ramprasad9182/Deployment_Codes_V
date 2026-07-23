/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";

patch(OrderWidget.prototype, {
    get_total_quantity() {
        return this.props.lines.filter(line => !line.is_reward_line)
                .reduce((total, line) => total + (line.quantity || 0), 0);
    },
});
