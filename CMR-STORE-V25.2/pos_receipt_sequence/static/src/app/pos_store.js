/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";

patch(PosStore.prototype, {
    // @Override
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.db.old_uid = "";
    },    
});
