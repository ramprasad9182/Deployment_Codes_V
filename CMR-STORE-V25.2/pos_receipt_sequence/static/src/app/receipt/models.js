/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";

patch(Order.prototype, {
   setup(_defaultObj, options) {
        super.setup(...arguments);
        this.sequence_code = this.sequence_code || "";
    },
    set_seq_code(seq_code) {
        this.sequence_code = seq_code;
    },

    async printChanges(cancelled) {
        var self = this;
        const orderChange = this.changesToOrder(cancelled);
        let isPrintSuccessful = true;
        const d = new Date();
        let hours = "" + d.getHours();
        hours = hours.length < 2 ? "0" + hours : hours;
        let minutes = "" + d.getMinutes();
        minutes = minutes.length < 2 ? "0" + minutes : minutes;
        for (const printer of this.pos.unwatched.printers) {
            const changes = this._getPrintingCategoriesChanges(
                printer.config.product_categories_ids,
                orderChange
            );
            // if (changes["new"].length > 0 || changes["cancelled"].length > 0) {
                if(self.pos.config.sale_receipt && self.pos.config.sale_receipt_sequence_id){
                    await self.env.services.orm.call(
                        'pos.order',
                        'create_pos_receipt_sequence',
                        [0,this.pos_session_id],

                    ).then(function(seq_code) {
                        self.set_seq_code(seq_code)
                        self.pos.db.old_uid = self.uid;
                        self.uid=seq_code;
                        self.name = _t("%s" , self.uid);
                    })

                    const printingChanges = {
                        new: changes["new"],
                        cancelled: changes["cancelled"],
                        table_name: this.pos.config.module_pos_restaurant
                            ? this.getTable().name
                            : false,
                        floor_name: this.pos.config.module_pos_restaurant
                            ? this.getTable().floor.name
                            : false,
                        name: this.name || "unknown order",
                        time: {
                            hours,
                            minutes,
                        },
                    };
                    const receipt = renderToElement("point_of_sale.OrderChangeReceipt", {
                        changes: printingChanges,
                    });
                    const result = await printer.printReceipt(receipt);
                    if (!result.successful) {
                        isPrintSuccessful = false;
                    }
                }else{
                    const printingChanges = {
                        new: changes["new"],
                        cancelled: changes["cancelled"],
                        table_name: this.pos.config.module_pos_restaurant
                            ? this.getTable().name
                            : false,
                        floor_name: this.pos.config.module_pos_restaurant
                            ? this.getTable().floor.name
                            : false,
                        name: this.name || "unknown order",
                        time: {
                            hours,
                            minutes,
                        },
                    };
                    const receipt = renderToElement("point_of_sale.OrderChangeReceipt", {
                        changes: printingChanges,
                    });
                    const result = await printer.printReceipt(receipt);
                    if (!result.successful) {
                        isPrintSuccessful = false;
                    }
                }
                
            // }
        }

        return isPrintSuccessful;
    }

});