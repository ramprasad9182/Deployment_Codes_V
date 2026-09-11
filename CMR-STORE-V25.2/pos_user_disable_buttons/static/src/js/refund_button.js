/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { RefundButton } from "@point_of_sale/app/screens/product_screen/control_buttons/refund_button/refund_button";
import { patch } from "@web/core/utils/patch";

patch(RefundButton.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.refund_access = !this.pos.user.allow_refund_button;
    },
});
