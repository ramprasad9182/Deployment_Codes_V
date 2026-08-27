/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PosDB } from "@point_of_sale/app/store/db";


patch(PosDB.prototype, {
    
    remove_unpaid_order(order) {
        super.remove_unpaid_order(...arguments)
        var orders = this.load("unpaid_orders", []);
        orders = orders.filter((o) => o.id !== this.old_uid);
        this.save("unpaid_orders", orders);
    },
    
});
