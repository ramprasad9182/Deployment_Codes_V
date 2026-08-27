/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { patch } from "@web/core/utils/patch";

patch(ActionpadWidget.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.customer_access = !this.pos.user.allow_customer_selection;
        this.payment_access = !this.pos.user.allow_payment_button;
    },
});
