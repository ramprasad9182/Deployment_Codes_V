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
            const { name, ref } = stockLot;
            if (stockLot.product_id && stockLot.product_id[0]) {
                if (!this.stock_lots_by_product_id[stockLot.product_id[0]]) {
                    this.stock_lots_by_product_id[stockLot.product_id[0]] = {};
                }
            }
            if (name) {
                this.stock_lots_by_name[name] = { stockLot };
                if (stockLot.product_id && stockLot.product_id[0]) {
                    this.stock_lots_by_product_id[stockLot.product_id[0]][name] = { stockLot };
                }
            }
            if (ref && !this.stock_lots_by_name[ref]) {
                this.stock_lots_by_name[ref] = { stockLot };
                if (stockLot.product_id && stockLot.product_id[0] && !this.stock_lots_by_product_id[stockLot.product_id[0]][ref]) {
                    this.stock_lots_by_product_id[stockLot.product_id[0]][ref] = { stockLot };
                }
            }
        });
        console.log(this.stock_lots_by_name);
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

    async load_orders() {
        const res = await super.load_orders(...arguments);
        for (const order of this.orders) {
            order.block_auto_promotions = false;
        }
        return res;
    },

    load_server_orders() {
        const res = super.load_server_orders(...arguments);
        for (const order of this.orders) {
            order.block_auto_promotions = false;
        }
        return res;
    },

    _loadLoyaltyData() {
        super._loadLoyaltyData(); // Call the parent method

        for (const rule of this.rules) {
            rule.serial_ids = new Set(rule.serial_ids || []);
            if (rule.serial_nos && typeof rule.serial_nos === "string") {
                const manualList = rule.serial_nos.split(',').map(s => s.trim()).filter(Boolean);
                manualList.forEach(s => {
                    const lotObj = this.stock_lots_by_name?.[s]?.stockLot || this.stock_lots_by_name?.[s.toUpperCase()]?.stockLot;
                    if (lotObj && lotObj.id) {
                        rule.serial_ids.add(lotObj.id);
                    }
                });
            }
        }
        for (const reward of this.rewards) {
            reward.stock_lot_ids = new Set(reward.stock_lot_ids || []);
        }
    },

    getProgramsForLot(lotId) {
        const programsWithLot = [];
        if (!lotId || !this.programs) {
            return programsWithLot;
        }
        for (const program of this.programs) {
            let hasLot = false;
            if (program.rules) {
                for (const rule of program.rules) {
                    if (rule.serial_ids && rule.serial_ids.has(lotId)) {
                        hasLot = true;
                        break;
                    }
                }
            }
            if (!hasLot && program.rewards) {
                for (const reward of program.rewards) {
                    if (reward.stock_lot_ids && reward.stock_lot_ids.has(lotId)) {
                        hasLot = true;
                        break;
                    }
                }
            }
            if (hasLot) {
                programsWithLot.push(program.name);
            }
        }
        return programsWithLot;
    },
});

