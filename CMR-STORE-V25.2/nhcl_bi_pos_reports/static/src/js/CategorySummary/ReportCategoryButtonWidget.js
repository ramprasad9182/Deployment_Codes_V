/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { PopupCategoryWidget } from "@nhcl_bi_pos_reports/js/CategorySummary/PopupCategoryWidget";

export class ReportCategoryButtonWidget extends Component {
    static template = "nhcl_bi_pos_reports.ReportCategoryButtonWidget";

    setup() {
        this.pos = usePos();
    }

    async onClick(){
		var self = this;
		self.pos.popup.add(PopupCategoryWidget,{
            'title': 'Payment Summary',
		});
	}
   
}

ProductScreen.addControlButton({
    component: ReportCategoryButtonWidget,
    position: ["before", "SetFiscalPositionButton"],
    condition: function () {
        return this.pos.config.product_categ_summery;
    },
});
