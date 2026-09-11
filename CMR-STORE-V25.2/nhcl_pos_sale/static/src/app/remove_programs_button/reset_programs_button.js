/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class RemoveProgramsButton extends Component {
    static template = "nhcl_pos_sale.RemoveProgramsButton";

    setup() {
        this.pos = usePos();
    }
    // _isDisabled() {
    //     return !this.pos.get_order().isProgramsResettable();
    // }
    click() {
        this.pos.get_order()._removePrograms();
    }
}

ProductScreen.addControlButton({
    component: RemoveProgramsButton,
    condition: function () {
        return this.pos.programs.some((p) =>
            ["coupons", "promotion"].includes(p.program_type)
        );
    },
});
