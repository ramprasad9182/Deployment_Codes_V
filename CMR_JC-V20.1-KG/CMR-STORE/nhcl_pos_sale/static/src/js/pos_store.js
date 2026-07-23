/** @odoo-module */
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { EditListPopup } from "@point_of_sale/app/store/select_lot_popup/select_lot_popup";

patch(PosStore.prototype, {
         /**
         *Override PosGlobalState to load fields in pos session
         */
     async _processData(loadedData) {
        await super._processData(...arguments);
        this.hr_employee = loadedData['hr.employee'];
        this.stock_location = loadedData['stock.location'] || [];
     },



      async get_redeem_amount(id){

    return await this.orm.call("pos.session", "get_wallet_amount", [this.pos_session.id,id]);

     },

    // Pranav Start
    async getEditedPackLotLines(isAllowOnlyOneLot, packLotLinesToEdit, productName) {
        const { confirmed, payload } = await this.env.services.popup.add(EditListPopup, {
            title: _t("Lot/Serial Number(s) Required"),
            name: productName,
            isSingleItem: isAllowOnlyOneLot,
            array: packLotLinesToEdit,
        });
        if (!confirmed) {
            this.lot_serial_cancel = true;
            return;
        }
        // Segregate the old and new packlot lines
        const modifiedPackLotLines = Object.fromEntries(
            payload.newArray.filter((item) => item.id).map((item) => [item.id, item.text])
        );
        const newPackLotLines = payload.newArray
            .filter((item) => !item.id)
            .map((item) => ({ lot_name: item.text }));

        return { modifiedPackLotLines, newPackLotLines };
    },

    async addProductToCurrentOrder(product, options = {}) {
        if (Number.isInteger(product)) {
            product = this.db.get_product_by_id(product);
        }
        this.get_order() || this.add_new_order();

        options = { ...(await product.getAddProductOptions()), ...options };

        if (!Object.keys(options).length) {
            return;
        }

        // Add the product after having the extra information.
        if (this.lot_serial_cancel) {
            this.lot_serial_cancel = false;
            return;
        }
        await this.addProductFromUi(product, options);
        if (product.tracking == "serial") {
            this.selectedOrder?.selected_orderline?.set_quantity_by_lot();
        }
        this.numberBuffer.reset();
    },

//    async getEditedPackLotLines(isAllowOnlyOneLot, packLotLinesToEdit, productName) {
//        debugger;
//        const result = await super.getEditedPackLotLines(...arguments);
//
//        debugger;
//        if (!result) {
//            this.lot_serial_cancel = true;
//        }
//
//        return result;
//    },

//    async addProductToCurrentOrder(product, options = {}) {
//        debugger;
//        if (this.lot_serial_cancel) {
//            this.lot_serial_cancel = false;
//            return;
//        }
//        return super.addProductToCurrentOrder(...arguments);
//    },
    // Pranav Stop

});
