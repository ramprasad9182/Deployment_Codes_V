/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { PopupProductWidget } from "@nhcl_bi_pos_reports/js/ReportProductButton/PopupProductWidget";
export class ReportProductButtonWidget extends Component {
    static template = "nhcl_bi_pos_reports.ReportProductButtonWidget";

    setup() {
        this.pos = usePos();
    }

    async onClick(){
        var self = this;
        self.pos.popup.add(PopupProductWidget,{
            'title': 'Product Summary',
        });
    }
}

ProductScreen.addControlButton({
    component: ReportProductButtonWidget,
    position: ["before", "SetFiscalPositionButton"],
    condition: function () {
        return this.pos.config.product_summery;
    },
});