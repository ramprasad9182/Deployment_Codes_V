/** @odoo-module */
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class CustomButton extends Component {
    static template = "pos_discount_manager.CustomButton";
    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }
    async click() {
        const order = this.pos.get_order();
        const lines = order.get_orderlines();

        lines.forEach(line => {
            line.select_order_line = false;
        });

        const product = this.pos.db.get_product_by_id(
            this.pos.config.discount_product_id[0]
        );

        const discountLines = lines.filter(
            line => line.get_product() === product
        );

        const discountedLines = lines.filter(line =>
            (line.discount || 0) > 0 || (line.gdiscount || 0) > 0 || (line.fix_discount || 0) > 0
        );

        if (discountLines.length === 0 && discountedLines.length === 0) {
            await this.popup.add(ErrorPopup, {
                title: _t("No discount product found"),
                body: _t("Discount is Not Applied to Any Product."),
            });
            return;
        }

        // remove discount product lines
        discountLines.forEach(line => order._unlinkOrderline(line));

        // reset discounts
        discountedLines.forEach(line => {
            line.set_discount(0);
            if (line.set_gdiscount) {
                line.set_gdiscount(0);
            }
            if (line.fix_discount) {
                line.set_fix_discount(0);
            }
        });

        order._updateRewards();
    }

}
ProductScreen.addControlButton({
    component: CustomButton,
    condition: function () {
        return true;
    },
});
