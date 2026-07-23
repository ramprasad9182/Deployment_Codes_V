/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { Domain, InvalidDomainError } from "@web/core/domain";
import { PosLoyaltyCard } from "@pos_loyalty/overrides/models/loyalty";

const { DateTime } = luxon;
const COUPON_CACHE_MAX_SIZE = 4096;

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(loadedData);
        this.stock_lot = loadedData['stock.lot'];
        this._loadStockLots(this.stock_lot || []);
//        this._loadPosOrderLines(loadedData['pos.order.line'] || []);
    },

    _loadStockLots(stockLots) {
        this.stock_lots_by_name = {};
        this.stock_lots_by_product_id = {};
        stockLots.forEach(stockLot => {
            const { name} = stockLot;
            if (!this.stock_lots_by_product_id[stockLot.product_id[0]]) {
                this.stock_lots_by_product_id[stockLot.product_id[0]] = [];
            }
            this.stock_lots_by_name[name] = {
                stockLot // Include stockLot object itself if needed
            };
            this.stock_lots_by_product_id[stockLot.product_id[0]][name] = {
                stockLot
            };
        });
        console.log(this.stock_lots_by_name)
    },

//    _loadPosOrderLines(PosOrderLines) {
//        this.pos_line_by_id = {};
//        PosOrderLines.forEach(PosOrderLine => {
//            const { id } = PosOrderLine;
//            this.pos_line_by_id[id] = {
//                PosOrderLine // Include PosOrderLine object itself if needed
//            };
//        });
//        console.log(this.pos_line_by_id)
//    },

    _loadLoyaltyData() {
        super._loadLoyaltyData(); // Call the parent method

        for (const rule of this.rules) {
            rule.serial_ids = new Set(rule.serial_ids);
            console.log(rule.serial_ids)
        }
    },
});
