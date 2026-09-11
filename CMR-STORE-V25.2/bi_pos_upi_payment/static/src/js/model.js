/** @odoo-module */
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this._loadPOSUPIPayment(loadedData["pos.upi.payment"]);
    },
    _loadPOSUPIPayment(upi_payments) {
        var self = this;
        let upi_methods = {};
        var payment_methods = self.payment_methods;
        for (var i = 0; i < payment_methods.length; i++) {
            if (payment_methods[i].upi) {
                for (var j = 0; j < payment_methods[i].pos_upi_payment_ids.length; j++) {
                    for (var k = 0; k < upi_payments.length; k++) {
                        if (payment_methods[i].pos_upi_payment_ids[j] === upi_payments[k].id) {
                            if (self.config.id === upi_payments[k].pos_config_id[0]) {
                                upi_methods[k] = upi_payments[k];
                            }
                        }
                    }
                }
            }
        }
        self.db.pos_upi_payments = upi_methods;
    }
})

    
