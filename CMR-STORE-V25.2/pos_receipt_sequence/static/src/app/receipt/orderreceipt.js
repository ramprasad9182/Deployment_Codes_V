/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";


patch(OrderReceipt.prototype, {
    setup() {
        super.setup();
        var self= this;
        this.orm = useService("orm");
    },

    get sequence(){
        var self=this;
        let order=self.pos.get_order();
        return order.sequence_code

    },
});