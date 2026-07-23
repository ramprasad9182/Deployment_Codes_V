/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.new_order_access = !this.pos.user.allow_new_order_button;
        this.delete_order_access = this.pos.user.allow_delete_order_button;
    },
});
