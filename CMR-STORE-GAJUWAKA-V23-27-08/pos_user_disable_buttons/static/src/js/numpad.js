/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Numpad } from "@point_of_sale/app/generic_components/numpad/numpad";
import { patch } from "@web/core/utils/patch";

patch(Numpad.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.numpad_access = this.pos.user.allow_numpad_button;
        this.qty_access = this.pos.user.allow_qty_button;
        this.price_access = this.pos.user.allow_price_button;
        this.plusminus_access = this.pos.user.allow_plusminus_button;
        this.remove_access = this.pos.user.allow_remove_button;
        this.discount_access = this.pos.user.allow_discount_button;
    },

    getNumPadAccess(button) {
        var numberPad = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '.']
        if (!this.numpad_access && numberPad.includes(button.value)) {
            return true
        }
        if (!this.qty_access && button.value == 'quantity'){
            return true;
        }
        if (!this.discount_access && button.value == 'discount') {
            return true;
        }
        if (!this.price_access && button.value == 'price') {
            return true;
        }
        if (!this.plusminus_access && button.value == '-') {
            return true;
        }
        if (!this.remove_access && button.value == 'Backspace') {
            return true;
        }
//        Pranav Start
//      Restrict to apply discount on line
        if (button.value == 'discount') {
            return true;
        }
//        Stop
        return button.disabled;
    }
});
