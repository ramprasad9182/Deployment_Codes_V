/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { PopupLocationWidget } from "@nhcl_bi_pos_reports/js/AuditReport/PopupLocationWidget";

export class ReportLocationButtonWidget extends Component {
    static template = "nhcl_bi_pos_reports.ReportLocationButtonWidget";

    setup() {
        this.pos = usePos();
    }

    async onClick(){
        var self = this;
        self.pos.popup.add(PopupLocationWidget,{
            'title': 'Audit Report',
        });
    }
   
}

ProductScreen.addControlButton({
    component: ReportLocationButtonWidget,
    position: ["before", "SetFiscalPositionButton"],
    condition: function () {
        return this.pos.config.loc_summery;
    },
});


