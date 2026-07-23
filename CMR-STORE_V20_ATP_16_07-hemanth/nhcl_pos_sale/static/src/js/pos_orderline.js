/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { CustomButtonPopup } from "@nhcl_pos_sale/app/custom_popup/custom_popup";
import { Orderline, Order } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";
import { parseFloat as oParseFloat } from "@web/views/fields/parsers";

import {
    formatFloat,
    roundDecimals as round_di,
    roundPrecision as round_pr,
    floatIsZero,
} from "@web/core/utils/numbers";

patch(Orderline.prototype, {
    setup(_defaultObj, options) {
        // Call the original setup method
        super.setup(...arguments);
        // Initialize empNo
        this.empNo = this.empNo || "";
        this.badge = "" || "";
        this.empId = this.empId || 0;
        this.proId = false;
        this.barcode = "";
        this.product_tax = "";
        this.product_mrp = "";
        this.discount_reward = 0;
        this.gdiscount = this.gdiscount || 0;
        this.promodisclines = [];
        this.discount_value = this.discount_value || 0;
        this.discount_minimum_amount = 0;
    },

    export_as_JSON() {
        // Call the original export_as_JSON method
        const json = super.export_as_JSON();
        // Return the extended JSON
        return {
            ...json,
            employe_no: this.get_emp_no(),
            badge_id: this.get_badge_id(),
            employ_id: this.get_employe_id(),
            gdiscount: this.get_gdiscount(),
            disc_lines: this.get_disclines(),
            discount_reward: this.get_discount_reward(),
             discount_minimum_amount: this.get_discount_minimum_amount(),
            discount_value: this.get_discount_value(),
            discount_amount: this.get_discount_amount(),
            gdiscount_amount: this.get_gdiscount_amount(),
        };
    },

    init_from_JSON(json) {
        // Call the original init_from_JSON method
        super.init_from_JSON(...arguments);
        // Set empNo from JSON
        this.set_emp_no(json.employe_no);
        this.set_badge_id(json.badge_id);
        this.set_employee_id(json.employ_id);
        this.set_gdiscount(json.gdiscount);
        this.set_discount_reward(json.discount_reward);
        this.set_discount_value(json.discount_value);
        this.set_discount_amount(json.discount_amount);
        this.set_gdiscount_amount(json.gdiscount_amount);
         this.set_discount_minimum_amount(json.discount_minimum_amount);
    },

    set_gdiscount(gdiscount) {
        this.gdiscount = gdiscount;
    },

    set_discount_reward(discount_reward) {
        this.discount_reward = discount_reward;
    },

    set_discount_amount(discount_amount) {
        this.discount_amount = discount_amount;
    },

    set_gdiscount_amount(gdiscount_amount) {
        this.gdiscount_amount = gdiscount_amount;
    },

     set_discount_minimum_amount(discount_minimum_amount) {
        this.discount_minimum_amount = discount_minimum_amount;
    },
    get_discount_minimum_amount() {
        return this.discount_minimum_amount;
    },

    set_discount_value(discount_value) {
        const digits = this.pos.dp["Product Price"];
        this.discount_value = parseFloat(round_di(discount_value || 0, digits).toFixed(digits));
    },

    get_disclines() {
        return this.promodisclines;
    },

    get_gdiscount() {
        return this.gdiscount;
    },

    get_discount_reward() {
        return this.discount_reward;
    },

     get_discount_value() {
        return this.discount_value;
    },

    getDisplayData() {
        const lotName =
            this.pack_lot_lines.length > 0
                ? this.pack_lot_lines[0].lot_name
                : null;

        const stockLot = this.pos.stock_lots_by_name[lotName];

        const ref = stockLot ? stockLot.stockLot.ref : null;
        let mrp = stockLot ? stockLot.stockLot.rs_price : null;
        //         if (this.reward_id){
        //        const reward = this.pos.reward_by_id[this.reward_id];
        //        if (reward.reward_type == 'discount_on_product'){
        //         mrp = reward.product_price
        //        }
        //        }
        var tax = "";
        const nhcl_taxes = this.get_taxes();
        if (nhcl_taxes.length > 0) {
            tax = nhcl_taxes[0].name;
        }

        //        Pranav ----- START -----
        let count = 0
        this.order.get_orderlines().map((line) => {
            count += 1
            line.nf_sequence = count
        })
        //        ----- Finish -----
        // Call the original getDisplayData method
        return {
            ...super.getDisplayData(),
            line_obj: this,
            empNo: this.get_emp_no(),
            badge: this.get_badge_id(),
            barcode: ref,
            product_tax: tax,
            product_mrp: mrp,
            is_reward_line: this.is_reward_line, // Pranav
            nf_sequence: this.nf_sequence, // Pranav
            gdiscount: this.get_gdiscount(),
            discount_value: this.get_discount_value(),
            discount_amount: this.get_discount_amount(),
            gdiscount_amount: this.get_gdiscount_amount(),
        };
    },

    //    can_be_merged_with(orderline) {
    //        // Call the original can_be_merged_with method
    //        const result = super.can_be_merged_with(orderline);
    //        // Return the result of merge check including empNo comparison
    //        return result && orderline.proId === true
    //    },

    set_emp_no(no) {
        // Set empNo with default empty string if no value is provided
        this.empNo = no || "";
    },
    set_badge_id(no) {
        // Set badge with default empty string if no value is provided
        this.badge = no || "";
    },

    set_employee_id(no) {
        // Set employee with default empty string if no value is provided
        this.empId = no;
    },

    async set_quantity(quantity, keep_price) {
        // Restrict serial-tracked products to qty = 1


        if (
            (this.product.nhcl_product_type === "unbranded" || this.product.nhcl_product_type === "branded") &&
            this.product.tracking === "serial" &&
            quantity > 1
        ) {
            return this.pos.env.services.popup.add(ErrorPopup, {
                title: _t("Quantity Not Allowed"),
                body: _t(
                    "Serial-tracked products can only have quantity 1 per line."
                ),
            });

            quantity = 1; // Enforce quantity = 1
        }

        // Handle lot-tracked products
        else if (this.product.tracking === "lot" && this.pack_lot_lines) {

            try {
                const lot_name = this.pack_lot_lines.at(0).lot_name;

                // Fetch the lot record
                const lot_data = await this.pos.orm.call(
                    "stock.lot",
                    "search_read",
                    [
                        [["name", "=", lot_name]],
                        [
                            "id",
                            "name",
                            "product_id",
                            "location_id",
                            "product_qty",
                        ],
                    ]
                );

                if (lot_data.length > 0) {
                    const lot_id = lot_data[0].id;

                    const lot_qty_available = lot_data[0].product_qty;

                    // Prevent over-quantity
                    if (quantity > lot_qty_available) {
                        return this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("Not Enough Quantity"),
                            body: _t(
                                "Only " +
                                    lot_qty_available +
                                    " units are available in Lot " +
                                    lot_name
                            ),
                        });
                    }
                }
            } catch (error) {
                console.error("Error checking lot quantity:", error);
            }
            if (this.order) {
            this.order._updateRewards();
            }

        }
//this.order._updateRewards();
        // Apply quantity update if checks pass
         if (quantity === '0')
        {
        this.set_discount(0)
        }
        return super.set_quantity(quantity, keep_price);
    },

    get_emp_no() {
        // Return empNo
        return this.empNo;
    },
    get_badge_id() {
        // Return badge
        return this.badge;
    },

    get_employe_id() {
        // Return empId
        return this.empId;
    },

    get_unit_price() {
        const digits = this.pos.dp["Product Price"];
        if (this.order && this.order.locked) {
            return parseFloat(round_di(this.price || 0, digits).toFixed(digits));
        }
        const rewardId = this.reward_id || this.discount_reward;
        const reward = this.pos.reward_by_id[rewardId];
        if (reward && this.reward_product_id) {
            let reward_product = this.order.get_orderlines().find((line) => line.product.id === this.reward_product_id);
            console.log("reward_product", reward_product);
            if (reward_product && reward_product.pack_lot_lines) {
                const packLotLines = reward_product.pack_lot_lines;
                let k;
                packLotLines.forEach((pack) => {k = pack.lot_name;});
                const stockLot = this.pos.stock_lots_by_name[k];
                if (stockLot && stockLot.stockLot.rs_price > 0) {
                    lot_price = this.quantity * -stockLot.stockLot.rs_price;
                    console.log("lot_price", lot_price);
                    return parseFloat(round_di(lot_price, digits).toFixed(digits));
                }
            }
            return parseFloat(round_di(this.price || 0, digits).toFixed(digits));
        } else if (reward && rewardId && reward.reward_type == "discount_on_product") {
            if (reward.product_price > 0) {
                var lot_price = reward.product_price;
                return parseFloat(round_di(lot_price, digits).toFixed(digits));
            }
        } else if (reward && rewardId && reward.buy_with_reward_price === "yes") {
            if (reward.reward_price > 0) {
                // OLD BUY3@599 => Exact divide => 199.67 + 199.67 + 199.67 = 599.01
                var lot_price = reward.reward_price / reward.buy_product_value;
                // // NEW BUY3@599 => Divide with absolute value => 199 + 199 + 201 = 599
                // var lot_price = this.calculateRewardShare()[this.cid];
                return parseFloat(round_di(lot_price, digits).toFixed(digits));
            }
        } else if (this.pack_lot_lines) {
            const packLotLines = this.pack_lot_lines;
            let k;
            packLotLines.forEach((pack) => {k = pack.lot_name;});
            const stockLot = this.pos.stock_lots_by_name[k];
            if (stockLot && stockLot.stockLot.rs_price > 0) {
                var lot_price = stockLot.stockLot.rs_price;
                console.log("UNIT PRICE", lot_price);
                return parseFloat(round_di(lot_price, digits).toFixed(digits));
            }
        } else {
            console.log("get unit price ", this);
            // round and truncate to mimic _symbol_set behavior
            return parseFloat(round_di(this.price || 0, digits).toFixed(digits));
        }
    },

    get_discount_amount_str() {
        const digits = this.pos.dp["Product Price"];
        return round_di(this.discount_amount || 0, digits).toFixed(digits);
    },

    get_discount_amount() {
        const price = this.get_unit_price();
        const qty = this.get_quantity();
        const percent = (this.discount || 0);
        const discount_amount = price * qty * percent / 100;
        const digits = this.pos.dp["Product Price"];
        this.discount_amount = parseFloat(round_di(discount_amount || 0, digits).toFixed(digits))
        return this.discount_amount;
    },

    get_gdiscount_amount_str() {
        const digits = this.pos.dp["Product Price"];
        return round_di(this.gdiscount_amount || 0, digits).toFixed(digits);
    },

    get_gdiscount_amount() {
        let price = this.get_unit_price();
        if (this.get_discount_amount()) {
            price -= this.get_discount_amount()
        }
        const qty = this.get_quantity();
        const percent = (this.gdiscount || 0);
        const gdiscount_amount = price * qty * percent / 100;
        const digits = this.pos.dp["Product Price"];
        this.gdiscount_amount = parseFloat(round_di(gdiscount_amount || 0, digits).toFixed(digits));
        return this.gdiscount_amount;
    },

    get_full_product_name() {
        const name = this.full_product_name || this.product.display_name || "";
        return name.split("(")[0].trim();
    },

    // /**
    //  * Dynamically distributes the bundle reward price across all eligible sibling lines.
    //  *
    //  * For a "buy N for ₹X" promotion, this splits X evenly across the N units,
    //  * giving each line its per-unit share. Any rounding remainder (fractions of a rupee)
    //  * is added to the LAST line so the total is always exactly reward_price (Only for ODD bundle sizes).
    //  *
    //  * Example: buy 2 for ₹1399
    //  * - Line 1 qty=1 → ₹699.5
    //  * - Line 2 qty=1 → ₹699.5
    //  * - Total: ₹1399
    //  *
    //  * @returns {Object} Map of { [line.cid]: priceForThisLine }
    //  */
    // calculateRewardShare() {
    //     const order = this.order;
    //     if (!order || !this.reward_id) return {};
    //
    //     // Get the reward object so we can read its actual price and bundle size
    //     const reward = this.pos.reward_by_id[this.reward_id];
    //     if (!reward || !reward.reward_price || !reward.buy_product_value) return {};
    //
    //     const bundlePrice = reward.reward_price;        // e.g. 1399 for "2 for 1399"
    //     const bundleSize  = reward.buy_product_value;   // e.g. 2
    //
    //     // Collect all sibling lines that share this same reward
    //     const siblingLines = order.get_orderlines().filter(
    //         line => line.reward_id === this.reward_id
    //     );
    //
    //     if (siblingLines.length === 0) return {};
    //
    //     // Count total units across all sibling lines
    //     let totalQty = 0;
    //     siblingLines.forEach(line => {
    //         totalQty += Math.round(line.get_quantity());
    //     });
    //
    //     // How many complete bundles and how many leftover units?
    //     const completeBundles  = Math.floor(totalQty / bundleSize);
    //     const leftoverUnits    = totalQty % bundleSize;
    //
    //     // Per-unit price inside a full bundle
    //     const pricePerBundleUnit = bundlePrice / bundleSize;
    //
    //     // Build a pool of per-unit prices for every unit in the order
    //     const unitPricesPool = [];
    //
    //     // Complete bundles distribution
    //     for (let b = 0; b < completeBundles; b++) {
    //         if (bundleSize % 2 === 0) {
    //             // EVEN bundle size: Divide exactly across all units to avoid rounding asymmetry
    //             for (let u = 0; u < bundleSize; u++) {
    //                 unitPricesPool.push(pricePerBundleUnit);
    //             }
    //         } else {
    //             // ODD bundle size: Floor the base and push remainder to the last unit
    //             const baseUnitPrice  = Math.floor(pricePerBundleUnit);
    //             const remainder      = Math.round(bundlePrice - baseUnitPrice * bundleSize);
    //             for (let u = 0; u < bundleSize; u++) {
    //                 if (u === bundleSize - 1) {
    //                     // Last unit in bundle absorbs any rounding remainder
    //                     unitPricesPool.push(baseUnitPrice + remainder);
    //                 } else {
    //                     unitPricesPool.push(baseUnitPrice);
    //                 }
    //             }
    //         }
    //     }
    //
    //     // Leftover units (not enough to form a full bundle)
    //     for (let u = 0; u < leftoverUnits; u++) {
    //         unitPricesPool.push(this.price || 0);
    //     }
    //
    //     // Distribute pool values across sibling lines proportionally to their quantities
    //     const shareMapping = {};
    //     let poolIndex = 0;
    //
    //     for (const line of siblingLines) {
    //         const lineQty = Math.round(line.get_quantity());
    //         let lineTotalShare = 0;
    //
    //         for (let i = 0; i < lineQty; i++) {
    //             if (poolIndex < unitPricesPool.length) {
    //                 lineTotalShare += unitPricesPool[poolIndex];
    //                 poolIndex++;
    //             }
    //         }
    //
    //         shareMapping[line.cid] = lineTotalShare;
    //     }
    //
    //     return shareMapping;
    // },
});