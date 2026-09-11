/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { evaluateExpr, evaluateBooleanExpr } from "@web/core/py_js/py";
import {
    roundPrecision as round_pr,
} from "@web/core/utils/numbers";

function matchTaxBracket(taxBracket, price) {
    if (!taxBracket) {
        return false;
    }
    let min = taxBracket.min_amount || 0;
    let max = taxBracket.max_amount || 0;
    if (min === 0 && max === 0) {
        if (taxBracket.amount === 5) {
            min = 0;
            max = 1000;
        } else if (taxBracket.amount === 12 || taxBracket.amount === 18) {
            min = 1000.01;
            max = 99999999;
        }
    }
    return price >= min && price <= max;
}

patch(Orderline.prototype, {
    // // OLD
    // get_applicable_taxes() {
    //     let lot_price = this.get_unit_price();
    //     if (this.pack_lot_lines) {
    //         const packLotLines = this.pack_lot_lines;
    //         let k;
    //         packLotLines.forEach((pack) => {
    //             k = pack.lot_name;
    //         });
    //         const stockLot = this.pos.stock_lots_by_name[k];
    //         if (stockLot && stockLot.stockLot.rs_price > 0) {
    //             lot_price = stockLot.stockLot.rs_price;
    //         }
    //     }
    //     // var price_unit = lot_price * (1.0 - this.get_discount() / 100.0);
    //     // price_unit = price_unit * (1.0 - this.gdiscount / 100.0);
    //     var price_unit = this.get_price_with_tax();
    //
    //     // Shenaningans because we need
    //     // to keep the taxes ordering.
    //
    //     let taxes_ids;
    //     if (this.product.taxes_id.length >= 2) {
    //         var selectedTaxIds = [];
    //         for (let i = 0; i < this.product.taxes_id.length; i++) {
    //             let taxBracket = this.pos.taxes_by_id[this.product.taxes_id[i]];
    //             if (
    //                 price_unit >= taxBracket.min_amount &&
    //                 price_unit <= taxBracket.max_amount
    //             ) {
    //                 selectedTaxIds = [this.product.taxes_id[i]];
    //                 break;
    //             }
    //         }
    //
    //         taxes_ids = selectedTaxIds;
    //     } else {
    //         taxes_ids = this.tax_ids || this.get_product().taxes_id;
    //     }
    //
    //     var i;
    //     var ptaxes_ids = this.tax_ids || taxes_ids;
    //     var ptaxes_set = {};
    //     for (i = 0; i < ptaxes_ids.length; i++) {
    //         ptaxes_set[ptaxes_ids[i]] = true;
    //     }
    //     var taxes = [];
    //     if (!this.is_fix_discount_line) {
    //         for (i = 0; i < this.pos.taxes.length; i++) {
    //             if (ptaxes_set[this.pos.taxes[i].id]) {
    //                 taxes.push(this.pos.taxes[i]);
    //             }
    //         }
    //     }
    //     return taxes;
    // },
    //
    // get_taxes() {
    //     const product = this.get_product();
    //     let reward_original_product = false;
    //     let lot_price = this.get_unit_price();
    //     if (lot_price < 0) {
    //         lot_price = -lot_price;
    //     }
    //     if (this.pack_lot_lines) {
    //         const packLotLines = this.pack_lot_lines;
    //         let k;
    //         packLotLines.forEach((pack) => {
    //             k = pack.lot_name;
    //         });
    //         const stockLot = this.pos.stock_lots_by_name[k];
    //         if (stockLot && stockLot.stockLot.rs_price > 0) {
    //             lot_price = stockLot.stockLot.rs_price;
    //         }
    //     }
    //     if (this.pack_lot_lines === false && this.is_reward_line == true) {
    //         for (const line of this.order.orderlines) {
    //             // Check for dead tabs.
    //             if (line.product.id === this.reward_product_id) {
    //                 if (line.pack_lot_lines) {
    //                     const packLotLines = line.pack_lot_lines;
    //                     let k;
    //                     packLotLines.forEach((pack) => {
    //                         k = pack.lot_name;
    //                     });
    //                     const stockLot = this.pos.stock_lots_by_name[k];
    //                     if (stockLot && stockLot.stockLot.rs_price > 0) {
    //                         lot_price = stockLot.stockLot.rs_price;
    //                         reward_original_product = line.product;
    //                     }
    //                 }
    //             }
    //         }
    //     }
    //     let discount = parseFloat(this.get_discount()) || 0;
    //     let gdiscount = parseFloat(this.gdiscount) || 0;
    //     var price_unit = lot_price * (1.0 - discount / 100.0);
    //     price_unit = price_unit * (1.0 - gdiscount / 100.0);
    //     let taxes_ids;
    //     if (!this.reward_id && product.taxes_id.length >= 2) {
    //         let selectedTaxIds = [];
    //         for (let i = 0; i < product.taxes_id.length; i++) {
    //             let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //             if (
    //                 price_unit >= taxBracket.min_amount &&
    //                 price_unit <= taxBracket.max_amount
    //             ) {
    //                 selectedTaxIds = [product.taxes_id[i]];
    //                 break;
    //             }
    //         }
    //         taxes_ids = selectedTaxIds;
    //     } else if (
    //         this.pack_lot_lines === false &&
    //         this.is_reward_line == true
    //     ) {
    //         if (reward_original_product) {
    //             if (reward_original_product.taxes_id.length >= 2) {
    //                 let selectedTaxIds = [];
    //                 for (
    //                     let i = 0;
    //                     i < reward_original_product.taxes_id.length;
    //                     i++
    //                 ) {
    //                     let taxBracket =
    //                         this.pos.taxes_by_id[
    //                             reward_original_product.taxes_id[i]
    //                         ];
    //                     if (
    //                         price_unit >= taxBracket.min_amount &&
    //                         price_unit <= taxBracket.max_amount
    //                     ) {
    //                         selectedTaxIds = [
    //                             reward_original_product.taxes_id[i],
    //                         ];
    //                         break;
    //                     }
    //                 }
    //                 taxes_ids = selectedTaxIds;
    //             }
    //         }
    //             else {
    //             let order_lines = this.order.orderlines
    //             let product = false
    //             if (order_lines.length>0){
    //             product = order_lines[0].product
    //             }
    //              let selectedTaxIds = [];
    //              if (this.product.display_name==='Gift Card'){
    //              selectedTaxIds = [];
    //              }
    //             else if (product.taxes_id.length >= 1) {
    //
    //                 for (let i = 0; i < product.taxes_id.length; i++) {
    //                     let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //                     if (price_unit >= taxBracket.min_amount && price_unit <= taxBracket.max_amount) {
    //                         selectedTaxIds = [product.taxes_id[i]];
    //                         break;
    //                     }
    //                 }
    //
    //             }
    //              taxes_ids = selectedTaxIds;
    //             }
    //     } else if (this.reward_id && product.taxes_id.length >= 2) {
    //         let selectedTaxIds = [];
    //         for (let i = 0; i < product.taxes_id.length; i++) {
    //             const reward = this.pos.reward_by_id[this.reward_id];
    //             if (reward.reward_type == "discount_on_product") {
    //                 let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //                 let price_unit = reward.product_price;
    //                 if (
    //                     price_unit >= taxBracket.min_amount &&
    //                     price_unit <= taxBracket.max_amount
    //                 ) {
    //                     selectedTaxIds = [product.taxes_id[i]];
    //                     break;
    //                 }
    //             }
    //              else if (reward.reward_type === "discount" && reward.buy_with_reward_price === 'yes') {
    //             let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //             let price_unit = reward.reward_price;
    //             if (
    //                 price_unit >= taxBracket.min_amount &&
    //                 price_unit <= taxBracket.max_amount
    //             ) {
    //                 selectedTaxIds = [product.taxes_id[i]];
    //                 break;
    //             }
    //         }
    //         }
    //         taxes_ids = selectedTaxIds;
    //     } else {
    //         taxes_ids = this.tax_ids || product.taxes_id;
    //     }
    //     if (taxes_ids) {
    //         taxes_ids = taxes_ids;
    //     } else {
    //         taxes_ids = [];
    //     }
    //
    //     if (this.is_fix_discount_line) {
    //         taxes_ids = [];
    //     }
    //     return this.pos.getTaxesByIds(taxes_ids);
    // },
    //
    // _getProductTaxesAfterFiscalPosition() {
    //     const product = this.get_product();
    //
    //     let lot_price = this.get_unit_price();
    //
    //     let price_unit = lot_price * (1.0 - this.get_discount() / 100.0);
    //
    //     price_unit = price_unit * (1.0 - this.gdiscount / 100.0);
    //
    //     let taxesIds;
    //     if (product.taxes_id.length >= 2) {
    //         let selectedTaxIds = [];
    //         for (let i = 0; i < product.taxes_id.length; i++) {
    //             let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //             if (
    //                 price_unit >= taxBracket.min_amount &&
    //                 price_unit <= taxBracket.max_amount
    //             ) {
    //                 selectedTaxIds = [product.taxes_id[i]];
    //                 break;
    //             }
    //         }
    //         taxesIds = selectedTaxIds;
    //     } else {
    //         taxesIds = this.tax_ids || product.taxes_id;
    //     }
    //
    //     taxesIds = taxesIds.filter((t) => t in this.pos.taxes_by_id);
    //
    //     if (this.is_fix_discount_line) {
    //         taxesIds = [];
    //     }
    //
    //     return this.pos.get_taxes_after_fp(
    //         taxesIds,
    //         this.order.fiscal_position
    //     );
    // },
    //
    // get_base_price() {
    //     var rounding = this.pos.currency.rounding;
    //     return round_pr(
    //         this.get_unit_price() * this.get_quantity() * (1 - (this.get_discount() + this.get_gdiscount()) / 100),
    //         rounding
    //     );
    // },
    //
    // get_all_prices(qty = this.get_quantity()) {
    //     let lot_price = this.get_unit_price();
    //     let reward_original_product = false;
    //     let discount = parseFloat(this.get_discount()) || 0;
    //     let gdiscount = parseFloat(this.get_gdiscount()) || 0;
    //     var price_unit = lot_price * (1.0 - discount / 100.0);
    //     price_unit = price_unit * (1.0 - gdiscount / 100.0);
    //
    //     if (this.fix_discount) {
    //         price_unit -= this.fix_discount;
    //     }
    //
    //     const order = this.order;
    //     var taxtotal = 0;
    //     var product = this.get_product();
    //     if (this.is_reward_line == true) {
    //         for (const line of this.order.orderlines) {
    //             // Check for dead tabs.
    //             if (line.product.id === this.reward_product_id) {
    //                 reward_original_product = line.product;
    //             }
    //         }
    //     }
    //     var taxes_ids;
    //     if (product.taxes_id.length >= 2) {
    //         let selectedTaxIds = [];
    //         for (let i = 0; i < product.taxes_id.length; i++) {
    //             let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
    //             if (
    //                 price_unit >= taxBracket.min_amount &&
    //                 price_unit <= taxBracket.max_amount
    //             ) {
    //                 selectedTaxIds = [product.taxes_id[i]];
    //                 break;
    //             }
    //         }
    //         taxes_ids = selectedTaxIds;
    //     } else if (this.is_reward_line == true && reward_original_product) {
    //         if (reward_original_product.taxes_id.length >= 2) {
    //             let selectedTaxIds = [];
    //             for (
    //                 let i = 0;
    //                 i < reward_original_product.taxes_id.length;
    //                 i++
    //             ) {
    //                 let taxBracket =
    //                     this.pos.taxes_by_id[
    //                         reward_original_product.taxes_id[i]
    //                     ];
    //                 if (
    //                     -price_unit >= taxBracket.min_amount &&
    //                     -price_unit <= taxBracket.max_amount
    //                 ) {
    //                     selectedTaxIds = [reward_original_product.taxes_id[i]];
    //                     break;
    //                 }
    //             }
    //             taxes_ids = selectedTaxIds;
    //         }
    //     } else {
    //         taxes_ids = this.tax_ids || product.taxes_id;
    //     }
    //     if (taxes_ids) {
    //         taxes_ids = taxes_ids.filter((t) => t in this.pos.taxes_by_id);
    //     } else {
    //         taxes_ids = [];
    //     }
    //
    //     if (this.is_fix_discount_line) {
    //         taxes_ids = [];
    //     }
    //
    //     var taxdetail = {};
    //     var product_taxes = this.pos.get_taxes_after_fp(
    //         taxes_ids,
    //         this.order.fiscal_position
    //     );
    //
    //
    //     console.log("product_taxes", product_taxes);
    //     var all_taxes = this.compute_all(
    //         product_taxes,
    //         price_unit,
    //         qty,
    //         this.pos.currency.rounding
    //     );
    //     var all_taxes_before_discount = this.compute_all(
    //         product_taxes,
    //         lot_price,
    //         qty,
    //         this.pos.currency.rounding
    //     );
    //     all_taxes.taxes.forEach(function (tax) {
    //         taxtotal += tax.amount;
    //         taxdetail[tax.id] = {
    //             amount: tax.amount,
    //             base: tax.base,
    //         };
    //     });
    //     return {
    //         priceWithTax: all_taxes.total_included,
    //         priceWithoutTax: all_taxes.total_excluded,
    //         priceWithTaxBeforeDiscount:
    //             all_taxes_before_discount.total_included,
    //         priceWithoutTaxBeforeDiscount:
    //             all_taxes_before_discount.total_excluded,
    //         tax: taxtotal,
    //         taxDetails: taxdetail,
    //     };
    // },

    // New
    get_applicable_taxes() {
        let lot_price = this.get_unit_price();
        let taxes_ids;
        let lot_id;
        if (this.pack_lot_lines) {
            const packLotLines = this.pack_lot_lines;
            let k;
            packLotLines.forEach((pack) => {k = pack.lot_name;});
            const stockLot = this.pos.stock_lots_by_name[k];
            if (stockLot && stockLot.stockLot.rs_price > 0) {
                lot_id = stockLot.stockLot;
                lot_price = stockLot.stockLot.rs_price;
                taxes_ids = stockLot.stockLot.sale_tax_ids;
            }
        }

        var price_unit = this.get_price_with_tax();

        if (lot_id && lot_id.sale_tax_ids?.length >= 2) {
            var selectedTaxIds = [];
            for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                if (matchTaxBracket(taxBracket, price_unit)) {
                    selectedTaxIds = [lot_id.sale_tax_ids[i]];
                    break;
                }
            }
            taxes_ids = selectedTaxIds;
        } else {
            if (lot_id && lot_id.sale_tax_ids?.length) {
                taxes_ids = this.tax_ids || lot_id.sale_tax_ids;
            }
            // else {
            //     taxes_ids = this.tax_ids || this.get_product().taxes_id;
            // }
        }

        var i;
        var ptaxes_ids = this.tax_ids || taxes_ids;
        var ptaxes_set = {};
        if (ptaxes_ids && ptaxes_ids.length > 0) {
            for (i = 0; i < ptaxes_ids.length; i++) {
                ptaxes_set[ptaxes_ids[i]] = true;
            }
        }
        var taxes = [];
        if (!this.is_fix_discount_line) {
            for (i = 0; i < this.pos.taxes.length; i++) {
                if (ptaxes_set[this.pos.taxes[i].id]) {
                    taxes.push(this.pos.taxes[i]);
                }
            }
        }
        return taxes;
    },

    get_taxes() {
        const product = this.get_product();
        let reward_original_product = false;
        let lot_price = this.get_unit_price();
        let taxes_ids;
        let lot_id;
        if (lot_price < 0) {
            lot_price = -lot_price;
        }
        if (this.pack_lot_lines) {
            const packLotLines = this.pack_lot_lines;
            let k;
            packLotLines.forEach((pack) => {k = pack.lot_name;});
            const stockLot = this.pos.stock_lots_by_name[k];
            if (stockLot && stockLot.stockLot.rs_price > 0) {
                lot_id = stockLot.stockLot;
                lot_price = stockLot.stockLot.rs_price;
            }
        }
        if (this.pack_lot_lines === false && this.is_reward_line == true) {
            for (const line of this.order.orderlines) {
                // Check for dead tabs.
                if (line.product.id === this.reward_product_id) {
                    if (line.pack_lot_lines) {
                        const packLotLines = line.pack_lot_lines;
                        let k;
                        packLotLines.forEach((pack) => {k = pack.lot_name;});
                        const stockLot = this.pos.stock_lots_by_name[k];
                        if (stockLot && stockLot.stockLot.rs_price > 0) {
                            lot_id = stockLot.stockLot;
                            lot_price = stockLot.stockLot.rs_price;
                            reward_original_product = line.product;
                        }
                    }
                }
            }
        }
        const rewardId = this.reward_id || this.discount_reward;
        let discount = parseFloat(this.get_discount()) || 0;
        let gdiscount = parseFloat(this.gdiscount) || 0;
        var price_unit = lot_price * (1.0 - discount / 100.0);
        price_unit = price_unit * (1.0 - gdiscount / 100.0);
        if (!rewardId && lot_id && lot_id.sale_tax_ids?.length >= 2) {
            let selectedTaxIds = [];
            for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                if (matchTaxBracket(taxBracket, price_unit)) {
                    selectedTaxIds = [lot_id.sale_tax_ids[i]];
                    break;
                }
            }
            taxes_ids = selectedTaxIds;
        } else if (this.pack_lot_lines === false && this.is_reward_line == true) {
            if (reward_original_product && lot_id) {
                if (lot_id && lot_id.sale_tax_ids?.length >= 2) {
                    let selectedTaxIds = [];
                    for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                        let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                        if (matchTaxBracket(taxBracket, price_unit)) {
                            selectedTaxIds = [lot_id.sale_tax_ids[i],];
                            break;
                        }
                    }
                    taxes_ids = selectedTaxIds;
                }
            } else {
                let order_lines = this.order.orderlines
                let product = false
                if (order_lines.length > 0) {
                    product = order_lines[0].product
                }
                let selectedTaxIds = [];
                if (this.product.display_name === 'Gift Card') {
                    selectedTaxIds = [];
                } else if (lot_id && lot_id.sale_tax_ids?.length >= 1) {

                    for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                        let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                        if (matchTaxBracket(taxBracket, price_unit)) {
                            selectedTaxIds = [lot_id.sale_tax_ids[i]];
                            break;
                        }
                    }

                }
                taxes_ids = selectedTaxIds;
            }
        } else if (rewardId && lot_id && lot_id.sale_tax_ids?.length >= 2) {
            let selectedTaxIds = [];
            for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                const reward = this.pos.reward_by_id[rewardId];
                if (reward.reward_type == "discount_on_product") {
                    let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                    let price_unit = reward.product_price;
                    if (matchTaxBracket(taxBracket, price_unit)) {
                        selectedTaxIds = [lot_id.sale_tax_ids[i]];
                        break;
                    }
                } else if (reward.reward_type === "discount" && reward.buy_with_reward_price === 'yes') {
                    let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                    let price_unit = reward.reward_price;
                    if (matchTaxBracket(taxBracket, price_unit)) {
                        selectedTaxIds = [lot_id.sale_tax_ids[i]];
                        break;
                    }
                }
                else {
                    let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                    // let price_unit = price_unit;
                    if (matchTaxBracket(taxBracket, price_unit)) {
                        selectedTaxIds = [lot_id.sale_tax_ids[i]];
                        break;
                    }
                }
            }
            taxes_ids = selectedTaxIds;
        } else {
            if (lot_id && lot_id.sale_tax_ids?.length) {
                // taxes_ids = this.tax_ids || lot_id.sale_tax_ids;
                taxes_ids = this.tax_ids || lot_id.sale_tax_ids;
            }
            // else {
            //     taxes_ids = this.tax_ids || product.taxes_id;
            // }
        }
        if (!taxes_ids) {
            taxes_ids = [];
        }

        if (this.is_fix_discount_line) {
            taxes_ids = [];
        }
        return this.pos.getTaxesByIds(taxes_ids);
    },

    _getProductTaxesAfterFiscalPosition() {
        const product = this.get_product();
        let lot_price = this.get_unit_price();
        let lot_id;
        if (this.pack_lot_lines) {
            const packLotLines = this.pack_lot_lines;
            let k;
            packLotLines.forEach((pack) => {k = pack.lot_name;});
            const stockLot = this.pos.stock_lots_by_name[k];
            if (stockLot && stockLot.stockLot.rs_price > 0) {
                lot_id = stockLot.stockLot;
                lot_price = stockLot.stockLot.rs_price;
            }
        }

        let price_unit = lot_price * (1.0 - this.get_discount() / 100.0);
        price_unit = price_unit * (1.0 - this.gdiscount / 100.0);

        let taxesIds;
        if (lot_id && lot_id.sale_tax_ids?.length >= 2) {
            let selectedTaxIds = [];
            for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                if (matchTaxBracket(taxBracket, price_unit)) {
                    selectedTaxIds = [lot_id.sale_tax_ids[i]];
                    break;
                }
            }
            taxesIds = selectedTaxIds;
        } else {
            if (lot_id && lot_id.sale_tax_ids?.length) {
                taxesIds = this.tax_ids || lot_id.sale_tax_ids;
            }
            // else {
            //     taxesIds = this.tax_ids || product.taxes_id;
            // }
        }

        taxesIds = taxesIds.filter((t) => t in this.pos.taxes_by_id);
        if (this.is_fix_discount_line) {
            taxesIds = [];
        }

        return this.pos.get_taxes_after_fp(taxesIds, this.order.fiscal_position);
    },

    get_base_price() {
        var rounding = this.pos.currency.rounding;
        return round_pr(
            this.get_unit_price() * this.get_quantity() * (1 - (this.get_discount() + this.get_gdiscount()) / 100),
            rounding
        );
    },

    get_price_without_tax_before_discount() {
        return this.get_all_prices().priceWithoutTaxBeforeDiscount;
    },

    get_all_prices(qty = this.get_quantity()) {
        const lot_price = this.get_unit_price();
        let lot_id;
        if (this.pack_lot_lines) {
            const packLotLines = this.pack_lot_lines;
            let k;
            packLotLines.forEach((pack) => {k = pack.lot_name;});
            const stockLot = this.pos.stock_lots_by_name[k];
            if (stockLot && stockLot.stockLot.rs_price > 0) {
                lot_id = stockLot.stockLot;
            }
        }

        let reward_original_product = false;
        let discount = parseFloat(this.get_discount()) || 0;
        let gdiscount = parseFloat(this.get_gdiscount()) || 0;
        var price_unit = lot_price * (1.0 - discount / 100.0);
        price_unit = price_unit * (1.0 - gdiscount / 100.0);

        if (this.fix_discount) {
            price_unit -= this.fix_discount;
        }

        const order = this.order;
        var taxtotal = 0;
        var product = this.get_product();
        if (this.is_reward_line == true) {
            for (const line of this.order.orderlines) {
                // Check for dead tabs.
                if (line.product.id === this.reward_product_id) {
                    reward_original_product = line.product;
                }
            }
        }
        var taxes_ids;
        if (lot_id && lot_id.sale_tax_ids?.length >= 2) {
            let selectedTaxIds = [];
            for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                if (matchTaxBracket(taxBracket, price_unit)) {
                    selectedTaxIds = [lot_id.sale_tax_ids[i]];
                    break;
                }
            }
            taxes_ids = selectedTaxIds;
        } else if (this.is_reward_line == true && reward_original_product) {
            if (lot_id && lot_id.sale_tax_ids?.length >= 2) {
                let selectedTaxIds = [];
                for (let i = 0; i < lot_id.sale_tax_ids?.length; i++) {
                    let taxBracket = this.pos.taxes_by_id[lot_id.sale_tax_ids[i]];
                    if (matchTaxBracket(taxBracket, -price_unit)) {
                        selectedTaxIds = [lot_id.sale_tax_ids[i]];
                        break;
                    }
                }
                taxes_ids = selectedTaxIds;
            }
        } else {
            if (lot_id && lot_id.sale_tax_ids?.length) {
                taxes_ids = this.tax_ids || lot_id.sale_tax_ids;
            }
            // else {
            //     taxes_ids = this.tax_ids || product.taxes_id;
            // }
        }
        if (taxes_ids) {
            taxes_ids = taxes_ids.filter((t) => t in this.pos.taxes_by_id);
        } else {
            taxes_ids = [];
        }

        if (this.is_fix_discount_line) {
            taxes_ids = [];
        }

        var taxdetail = {};
        var product_taxes = this.pos.get_taxes_after_fp(
            taxes_ids,
            this.order.fiscal_position
        );


        console.log("product_taxes", product_taxes);
        var all_taxes = this.compute_all(product_taxes, price_unit, qty, this.pos.currency.rounding);
        var all_taxes_before_discount = this.compute_all(product_taxes, lot_price, qty, this.pos.currency.rounding);

        all_taxes.taxes.forEach(function (tax) {
            taxtotal += tax.amount;
            taxdetail[tax.id] = {
                amount: tax.amount,
                base: tax.base,
            };
        });

        return {
            priceWithTax: all_taxes.total_included,
            priceWithoutTax: all_taxes.total_excluded,
            priceWithTaxBeforeDiscount:
            all_taxes_before_discount.total_included,
            priceWithoutTaxBeforeDiscount:
            all_taxes_before_discount.total_excluded,
            tax: taxtotal,
            taxDetails: taxdetail,
        };
    },
});
