/** @odoo-module */
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { SalesPersonsInfoPopup } from "@nhcl_pos_sale/app/salespersons_info_popup/salespersons_info_popup";


export class SalesPersonsInfoButton extends Component {
    static template = "nhcl_pos_sale.SalesPersonsInfoButton";
    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
    }
    async click() {
        const info = await this.orm.call("hr.employee", "search_read", [
            [['sale_employee', '=', 'yes']],
            ['id', 'name', 'barcode']
        ]);
        this.popup.add(SalesPersonsInfoPopup, { info: info });
    }

}
ProductScreen.addControlButton({
    component: SalesPersonsInfoButton,
    condition: function () {
        return true;
    },
});
