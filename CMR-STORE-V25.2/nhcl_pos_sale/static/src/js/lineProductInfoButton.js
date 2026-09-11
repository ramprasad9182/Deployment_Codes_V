/** @odoo-module */
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { LineProductInfoPopup } from "@nhcl_pos_sale/app/line_product_info_popup/line_product_info_popup";
import { useExternalListener } from "@odoo/owl";


export class LineProductInfoButton extends Component {
    static template = "nhcl_pos_sale.LineProductInfoButton";
    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        useExternalListener(window, "keydown", this._onKeyDown);
    }
    async click() {
        const selectedOrderline = this.pos.get_order().get_selected_orderline();
        if (selectedOrderline) {
            const info = await this.pos.getProductInfo(selectedOrderline.product, 1);
            this.popup.add(LineProductInfoPopup, { info: info, product: selectedOrderline.product, line: selectedOrderline });
        }
    }
    _onKeyDown(ev) {
        if (ev.target.tagName === "INPUT" ||ev.target.tagName === "TEXTAREA") {
            return;
        }
        if (ev.key === "F2") {
            ev.preventDefault();
            ev.stopPropagation();
            this.click();
        }
    }

}
ProductScreen.addControlButton({
    component: LineProductInfoButton,
    condition: function () {
        return true;
    },
});
