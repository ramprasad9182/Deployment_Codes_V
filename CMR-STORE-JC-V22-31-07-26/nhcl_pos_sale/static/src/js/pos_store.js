/** @odoo-module */
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { EditListPopup } from "@point_of_sale/app/store/select_lot_popup/select_lot_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(PosStore.prototype, {
    async showScreen(screenName, props) {
        if (screenName === 'PaymentScreen') {
            const order = this.get_order();
            if (order) {
                // Validation: Ensure every regular line has a Salesperson (Employee & Badge ID) assigned
                for (const line of order.get_orderlines()) {
                    if (!line.is_reward_line && !line.is_fix_discount_line) {
                        if (!line.badge || !line.empId) {
                            await this.env.services.popup.add(ErrorPopup, {
                                title: _t("Missing Salesperson"),
                                body: _t(`Please assign a salesperson (Employee & Badge ID) to product: ${line.product.display_name}`),
                            });
                            return false;
                        }
                    }
                }
                const lotNameToLine = {};
                const lotNames = [];
                const duplicateSerials = new Set();
                for (const line of order.get_orderlines()) {
                    if (line.product.tracking === 'serial') {
                        const lotLines = line.pack_lot_lines;
                        if (lotLines && lotLines.length > 0) {
                            for (const lotLine of lotLines) {
                                const lotName = lotLine.lot_name;
                                if (lotName) {
                                    lotNames.push(lotName);
                                    if (!lotNameToLine[lotName]) {
                                        lotNameToLine[lotName] = [];
                                    }
                                    lotNameToLine[lotName].push(line);
                                    if (lotNameToLine[lotName].length > 1) {
                                        duplicateSerials.add(lotName);
                                    }
                                }
                            }
                        }
                    }
                }

                if (duplicateSerials.size > 0) {
                    const duplicateList = Array.from(duplicateSerials);
                    await this.env.services.popup.add(ErrorPopup, {
                        title: _t("Duplicate Serial Numbers"),
                        body: _t(`The serial number(s) ${duplicateList.join(', ')} are duplicated in this order. Unique serial numbers can only be sold once.`),
                    });
                    return false;
                }

                if (lotNames.length > 0) {
                    const domain = [
                        ['name', 'in', lotNames],
                        ['product_qty_pos', '>', 0]
                    ];
                    try {
                        const availableLots = await this.orm.call('stock.lot', 'search_read', [domain, ['name', 'product_qty_pos']]);
                        const availableLotNames = new Set(availableLots.map(lot => lot.name));

                        const soldSerialLines = [];
                        for (const lotName of lotNames) {
                            if (!availableLotNames.has(lotName)) {
                                const lines = lotNameToLine[lotName];
                                for (const line of lines) {
                                    soldSerialLines.push({
                                        productName: line.product.display_name,
                                        serialNo: lotName
                                    });
                                }
                            }
                        }

                        if (soldSerialLines.length > 0) {
                            const bodyText = soldSerialLines.map(item => `${item.productName} (Serial: ${item.serialNo})`).join(', ');
                            await this.env.services.popup.add(ErrorPopup, {
                                title: _t("Serial Number(s) Already Sold"),
                                body: _t(`This product with serial no has been sold please scan again:\n${bodyText}`),
                            });
                            return false;
                        }
                    } catch (error) {
                        console.error("Error validating serial numbers before payment:", error);
                    }
                }
            }
        }
        return super.showScreen(...arguments);
    },
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
