/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { roundDecimals, roundPrecision } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

import { evaluateExpr, evaluateBooleanExpr } from "@web/core/py_js/py";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

function _newRandomRewardCode() {
    return (Math.random() + 1).toString(36).substring(3);
}

let pointsForProgramsCountedRules = {};

patch(Order.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments); // Call the original setup method

        // Initialize global discount
        this.global_discount = 0;
        this.is_rew = false;
        this.credit_note_amount = 0;
        this.credit_ids = [];
        this.credit_id = 0;
        this.credit_note_amounts = [];
        this.credit_partner;
        this.to_invoice = true;

        if (!options.json) {
            this.name = _t(
                "%s %s",
                this.pos.company.company_short_code,
                this.uid
            );
        }

        // Initialize global discount
    },

    pointsForPrograms(programs) {
        const restoredRewards = [];
        for (const line of this.get_orderlines()) {
            if (line.reward_id && !line.is_reward_line) {
                restoredRewards.push({ line, reward_id: line.reward_id });
                line.reward_id = false;
            }
        }
        try {
            return super.pointsForPrograms(...arguments);
        } finally {
            for (const { line, reward_id } of restoredRewards) {
                line.reward_id = reward_id;
            }
        }
    },

    _applyReward(reward, coupon_id, args) {
        const isGlobal = reward.is_global_discount;
        try {
            reward.is_global_discount = false;
            return super._applyReward(reward, coupon_id, args);
        } finally {
            reward.is_global_discount = isGlobal;
        }
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.credit_ids = this.credit_ids || [];
        json.credit_note_amounts = this.credit_note_amounts || [];
        json.credit_id = this.credit_id || 0;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.credit_ids = json.credit_ids || [];
        this.credit_note_amounts = json.credit_note_amounts || [];
        this.credit_id = json.credit_id || 0;
    },

    /**
     * Pure read-only eligibility check: determines whether `currentline` qualifies
     * for `reward` based on its lot serial number and rule conditions.
     *
     * IMPORTANT: This method must NEVER call set_discount() or set_discount_reward()
     * because those trigger Odoo's reactive pipeline (_updateRewards -> _getDiscountableOnSpecific)
     * causing infinite recursion. Discount application is done separately in _applyDiscountToLine().
     *
     * @param {Object} reward - The reward being evaluated
     * @param {Set}    applicableProducts - Set of applicable product IDs
     * @param {Object} currentline - The orderline being checked
     * @returns {boolean} true if the line is eligible for this reward
     */
    _isRewardProductPartOfRuleSerial(reward, applicableProducts, currentline) {
        // If this line has no lot/serial, it cannot be matched by serial rules
        if (!currentline.pack_lot_lines) {
            return false;
        }

        // --- Step 1: Resolve the lot name and ID from this line's pack_lot_lines ---
        let lotName;
        currentline.pack_lot_lines.forEach(pack => {
            lotName = pack.lot_name;
        });

        const stockLot = this.pos.stock_lots_by_name[lotName];
        if (!stockLot) {
            // Lot not found in POS data — cannot validate
            return false;
        }
        const lotId = stockLot.stockLot.id;
        console.log("Checking lot:", lotId, "for reward:", reward.id);

        // --- Step 2: Check if this lot is covered by any rule of the reward's program ---
        const matchingRules = reward.program_id.rules.filter(
            rule =>
                this._cmrLineMatchesRule(rule, currentline, reward.program_id) &&
                rule.serial_ids.has(lotId)
        );

        if (matchingRules.length === 0) {
            // This lot is not in any rule's serial list — line is not eligible
            return false;
        }

        // --- Step 3: Count how many eligible lot-lines are on the order (for quantity thresholds) ---
        // For 'grc' or 'serial' type, only count lines whose lot is in a rule of that type
        const isGrcOrSerialProgram =
            reward.program_id.rules.length > 0 &&
            ['grc', 'serial'].includes(reward.program_id.rules[0].type_filter);

        let totalProductQty = 0;
        const eligibleLines = [];

        for (const line of this.orderlines) {
            if (!applicableProducts.has(line.product.id)) {
                continue;
            }
            if (!line.pack_lot_lines) {
                continue;
            }

            // Resolve the lot of this sibling line
            let siblingLotName;
            line.pack_lot_lines.forEach(pack => {
                siblingLotName = pack.lot_name;
            });
            const siblingStockLot = this.pos.stock_lots_by_name[siblingLotName];
            const siblingLotId = siblingStockLot ? siblingStockLot.stockLot.id : false;

            if (isGrcOrSerialProgram) {
                // For GRC/Serial programs, only count lines whose lot is in a grc/serial-type rule
                const isInRule = reward.program_id.rules.some(
                    rule => ['grc', 'serial'].includes(rule.type_filter) && rule.serial_ids.has(siblingLotId)
                );
                if (isInRule) {
                    totalProductQty += 1;
                    eligibleLines.push(line);
                }
            } else {
                totalProductQty += line.get_quantity();
                eligibleLines.push(line);
            }
        }

        // --- Step 4: Check if the discount cap is already reached (short-circuit to eligible) ---
        const totalProductValue = eligibleLines.reduce((sum, line) => sum + line.get_price_with_tax(), 0);
        const discountAmount = totalProductValue * (reward.discount / 100);
        console.log("Computed discount amount:", discountAmount);
        if (reward.discount_max_amount > 0 && discountAmount > reward.discount_max_amount) {
            // Already over max discount cap — treat as eligible (capping happens later)
            return true;
        }

        // --- Step 5: Check minimum qty / amount thresholds for any rule ---
        const meetsThreshold = reward.program_id.rules.some(
            rule => {
                const useTax = rule.minimum_amount_tax_mode === "incl";
                let ruleQty = 0;
                let ruleValue = 0;

                for (const line of eligibleLines) {
                    if (this._cmrLineMatchesRule(rule, line, reward.program_id)) {
                        ruleQty += isGrcOrSerialProgram ? 1 : line.get_quantity();
                        ruleValue += useTax ? line.get_price_with_tax() : line.get_price_without_tax();
                    }
                }

                return ruleQty >= rule.minimum_qty && ruleValue >= rule.minimum_amount;
            }
        );

        return meetsThreshold;
    },

    /**
     * Applies discount to a single line AFTER the eligible line list has been fully built.
     * Called from the linesToDiscount loop in _getDiscountableOnSpecific.
     * Doing it here (not inside the eligibility check) prevents triggering
     * _updateRewards() during collection, which would cause infinite recursion.
     *
     * @param {Object} reward  - The reward being applied
     * @param {Object} line    - The orderline to apply the discount to
     */
    _applyDiscountToLine(reward, line) {
        if (reward.buy_with_reward_price === 'yes') {
            // For bundle/price-based rewards: clear percentage discount, tag reward
            line.set_discount(0);
            line.set_discount_reward(reward.id);
        } else {
            // For standard percentage discount rewards
            line.set_discount(reward.discount);
            line.set_discount_reward(reward.id);
        }
    },

    getClaimableRewards(coupon_id = false, program_id = false, auto = false) {

    if (this.couponPointChanges) {
            const allCouponPrograms = Object.values(this.couponPointChanges)
                .map((pe) => ({
                    program_id: pe.program_id,
                    coupon_id: pe.coupon_id,
                }))
                .concat(
                    this.codeActivatedCoupons.map((coupon) => ({
                        program_id: coupon.program_id,
                        coupon_id: coupon.id,
                    }))
                );

            const result = [];
            const totalWithTax = this.get_total_with_tax();
            const totalWithoutTax = this.get_total_without_tax();
            const totalIsZero = totalWithTax === 0;

            const globalDiscountLines = this._getGlobalDiscountLines();
            const globalDiscountPercent = globalDiscountLines.length
                ? this.pos.reward_by_id[globalDiscountLines[0].reward_id].discount
                : 0;

            if (allCouponPrograms.length===0){
                for (const currentline of this.orderlines){
                    if (currentline.discount&&currentline.discount_reward){
                        if (currentline.discount_minimum_amount>0 && currentline.discount_minimum_amount>currentline.get_unit_price()*this.orderlines.length){
                            currentline.set_discount(0);
                        }

                    }
                }
            }

            for (const couponProgram of allCouponPrograms) {

                const program = this.pos.program_by_id[couponProgram.program_id];

                if (
                    program.pricelist_ids.length > 0 &&
                    (!this.pricelist || !program.pricelist_ids.includes(this.pricelist.id))
                ) {
                    continue;
                }

                if (program.trigger === "with_code") {
                    if (!this._canGenerateRewards(program, totalWithTax, totalWithoutTax)) {
                        continue;
                    }
                }

                if (
                    (coupon_id && couponProgram.coupon_id !== coupon_id) ||
                    (program_id && couponProgram.program_id !== program_id)
                ) {
                    continue;
                }

                const points = this._getRealCouponPoints(couponProgram.coupon_id);
                let  totalProductQty = 0;
                for (const currentline of this.get_orderlines()){
                    if (currentline.quantity<=0){
                        continue;
                    }
                    if (currentline.pack_lot_lines){
                        const packLotLines = currentline.pack_lot_lines;
                        let k;
                        let lotId;
                        let lot_rsp;
                        packLotLines.forEach(pack => {
                            k = pack.lot_name
                        })
                        const stockLot = this.pos.stock_lots_by_name[k];
                        if (stockLot) {
                            lotId = stockLot.stockLot.id
                            lot_rsp = stockLot.stockLot.rsp
                        }
                        else {
                            lotId = false
                        }


                        if (
                            program.rules.filter(
                                (rule) => (['grc', 'serial'].includes(rule.type_filter)) && rule.serial_ids.has(lotId) && rule
                            ).length > 0
                        ) {
                            totalProductQty += 1;
                        }
                    }

                }

                for (let reward of program.rewards) {
                    if (points < reward.required_points) {
                        continue;
                    }

                    const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
                    if (rewardRuleId) {
                        const couponChange = this.couponPointChanges[couponProgram.coupon_id];
                        const appliedRules = couponChange ? (couponChange.appliedRules || []) : [];
                        if (!appliedRules.includes(rewardRuleId)) {
                            continue;
                        }
                    }

                    if (!rewardRuleId && totalProductQty > 0 && program.rules.some(r => r.type_filter === 'grc')) {
                        let enable_discount = false;
                        for (let i = 0; i < program.rules.length; i++) {
                            const rule = program.rules[i];
                            if (totalProductQty >= rule.minimum_qty) {
                                enable_discount = true;
                                reward = program.rewards[i];
                            }
                        }

                        if (!enable_discount) {
                            continue;
                        }
                    }

                    if (
                        reward.program_id.program_type === "coupons" &&
                        this.orderlines.find((l) => l.reward_id === reward.id)
                    ) {
                        continue;
                    }

                    if (auto && this.disabledRewards.has(reward.id)) {
                        continue;
                    }

                    if (reward.is_global_discount && reward.discount <= globalDiscountPercent) {
                        continue;
                    }
                    if (reward.reward_type === "discount" && totalIsZero) {
                        continue;
                    }

                    let unclaimedQty;
                    if (reward.reward_type === "product") {
                        if (!reward.multi_product) {
                            const product = this.pos.db.get_product_by_id(
                                reward.reward_product_ids[0]
                            );
                            if (!product) {
                                continue;
                            }
                            unclaimedQty = this._computeUnclaimedFreeProductQty(
                                reward,
                                couponProgram.coupon_id,
                                product,
                                points
                            );
                        }
                        if (!unclaimedQty || unclaimedQty <= 0) {
                            continue;
                        }
                    }

                    result.push({
                        coupon_id: couponProgram.coupon_id,
                        reward: reward,
                        potentialQty: unclaimedQty,
                    });
                }
            }
            return result;

        }
},

    removeOrderline(line) {
        const linesToRemove = line.getAllLinesInCombo();
        for (const lineToRemove of linesToRemove) {
            this._unlinkOrderline(lineToRemove);
            if (lineToRemove.reward_id){
            const reward = this.pos.reward_by_id[lineToRemove.reward_id];
            if (reward.buy_with_reward_price === "yes")
             {
             if(reward.program_id.rules.length==1)
            {
            this._getRewardLineValues({
            reward: reward,

        });
            }
            else if (reward.program_id.rules.length===2 && (reward.program_id.rewards.filter(
                (reward_id) => reward_id.required_points === reward.buy_product_value
            )).length>0)
            {
             this._getRewardLineValues({
            reward: reward,

        });


//
//
//                }

            }
            }



        }
            if (lineToRemove.refunded_orderline_id in this.pos.toRefundLines) {
                delete this.pos.toRefundLines[lineToRemove.refunded_orderline_id];
            }
        }
        this.select_orderline(this.get_last_orderline());
//        Pranav Start
        this.check_remove_unapplicable_reward_id();
//        Stop
        return true;
    },

    _getRewardLineValuesProduct(args) {
        const reward = args["reward"];
        const product = this.pos.db.get_product_by_id(
            args["product"] || reward.reward_product_ids[0]
        );

        let taxes_ids;
        if (product.taxes_id.length >= 2) {
            var selectedTaxIds = [];
            for (let i = 0; i < product.taxes_id.length; i++) {
                let taxBracket = this.pos.taxes_by_id[product.taxes_id[i]];
                if (
                    product.lst_price >= taxBracket.min_amount &&
                    product.lst_price <= taxBracket.max_amount
                ) {
                    selectedTaxIds = [product.taxes_id[i]];
                    break;
                }
            }

            taxes_ids = selectedTaxIds;

            console.log("price_unit", product);

            console.log(taxes_ids);
        } else {
            taxes_ids = product.taxes_id;
        }

        const points = this._getRealCouponPoints(args["coupon_id"]);
        const unclaimedQty = this._computeUnclaimedFreeProductQty(
            reward,
            args["coupon_id"],
            product,
            points
        );
        if (unclaimedQty <= 0) {
            return _t(
                "There are not enough products in the basket to claim this reward."
            );
        }
        const claimable_count = reward.clear_wallet
            ? 1
            : Math.min(
                  Math.ceil(unclaimedQty / reward.reward_product_qty),
                  Math.floor(points / reward.required_points)
              );
        const cost = reward.clear_wallet
            ? points
            : claimable_count * reward.required_points;
        // In case the reward is the product multiple times, give it as many times as possible
        const freeQuantity = Math.min(
            unclaimedQty,
            reward.reward_product_qty * claimable_count
        );
        //        const orderLines = this.get_orderlines();
        //        let price = 0.0
        //        let enable_free_discount = false;
        //        for (const currentline of orderLines) {
        //            if (currentline.pack_lot_lines){
        //                 const packLotLines = currentline.pack_lot_lines;
        //                 let k;
        //                 packLotLines.forEach(pack => {
        //                        k = pack.lot_name
        //                     })
        //                 let lotId = 0
        //                 const stockLot = this.pos.stock_lots_by_name[k];
        //                 if (stockLot) {
        //                 lotId = stockLot.stockLot.id
        //                 }
        //
        //
        //
        //            for (const rule of reward.program_id.rules){
        //                if (rule.any_product || rule.valid_product_ids.has(product.id) && rule.serial_ids.has(lotId))
        //                   {
        //                     price += currentline.price
        //                     if (price >= rule.minimum_amount){
        //                         enable_free_discount = true
        //                      }
        //                    console.log('price',price,rule.minimum_amount)
        //
        //                   }
        //
        //            }
        //       }
        //
        //}
        // if (enable_free_discount){
        //                     return [
        //            {
        //                product: reward.discount_line_product_id,
        //                price: -roundDecimals(
        //                    product.get_price(this.pricelist, freeQuantity),
        //                    this.pos.currency.decimal_places
        //                ),
        //                tax_ids: taxes_ids,
        //                quantity: args["quantity"] || freeQuantity,
        //                reward_id: reward.id,
        //                is_reward_line: true,
        //                reward_product_id: product.id,
        //                coupon_id: args["coupon_id"],
        //                points_cost: args["cost"] || cost,
        //                reward_identifier_code: _newRandomRewardCode(),
        //                merge: false,
        //            },
        //        ];
        //
        //
        //                 }
        console.log("free product", product.id);
        console.log(
            "discount_line_product_id",
            reward.discount_line_product_id
        );
        return [
            {
                product: reward.discount_line_product_id,
                price: -roundDecimals(
                    product.get_price(this.pricelist, freeQuantity),
                    this.pos.currency.decimal_places
                ),
//                tax_ids: taxes_ids,
                quantity: freeQuantity,
                reward_id: reward.id,
                is_reward_line: true,
                reward_product_id: product.id,
                coupon_id: args["coupon_id"],
                points_cost: args["cost"] || cost,
                reward_identifier_code: _newRandomRewardCode(),
                merge: false,
            },
        ];
    },

    _getDiscountableOnSpecific(reward) {

    const applicableProducts = reward.all_discount_product_ids;
    const linesToDiscount = [];
    const discountLinesPerReward = {};
    const orderLines = this.get_orderlines();
    const remainingAmountPerLine = {};
    for (const line of orderLines) {
        if (!line.get_quantity() || !line.price) {
            continue;
        }
        remainingAmountPerLine[line.cid] = line.get_price_with_tax();

        // Check if this line's product is in the discount-applicable set
        const productIsApplicable = applicableProducts.has(line.get_product().id);
        // Check if this is a reward line whose source product is applicable
        const isApplicableRewardLine =
            line.reward_product_id && applicableProducts.has(line.reward_product_id);

        if (
            (productIsApplicable && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line)) ||
            (isApplicableRewardLine && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line))
        ) {
            // NOTE: We do NOT call set_discount here. Discount is applied later in the
            // linesToDiscount loop AFTER this collection loop completes.
            // Calling set_discount here would trigger _updateRewards -> infinite recursion.
            linesToDiscount.push(line);
        } else if (line.reward_id) {
            const lineReward = this.pos.reward_by_id[line.reward_id];
            if (lineReward && lineReward.id === reward.id) {
                linesToDiscount.push(line);
            }
            if (!discountLinesPerReward[line.reward_identifier_code]) {
                discountLinesPerReward[line.reward_identifier_code] = [];
            }
            discountLinesPerReward[line.reward_identifier_code].push(line);
        }
    }

    let cheapestLine = false;
    for (const lines of Object.values(discountLinesPerReward)) {
        const lineReward = this.pos.reward_by_id[lines[0].reward_id];
        if (lineReward.reward_type !== "discount") {
            continue;
        }
        let discountedLines = orderLines;
        if (lineReward.discount_applicability === "cheapest") {
            cheapestLine = cheapestLine || this._getCheapestLine();
            discountedLines = [cheapestLine];
        } else if (lineReward.discount_applicability === "specific") {
            discountedLines = this._getSpecificDiscountableLines(lineReward);
        }
        if (!discountedLines.length) {
            continue;
        }
        const commonLines = linesToDiscount.filter((line) => discountedLines.includes(line));
        if (lineReward.discount_mode === "percent") {
            const discount = lineReward.discount / 100;
            for (const line of discountedLines) {
                if (line.reward_id) {
                    continue;
                }
                if (lineReward.discount_applicability === "cheapest") {
                    remainingAmountPerLine[line.cid] *= 1 - discount / line.get_quantity();
                } else {
                    remainingAmountPerLine[line.cid] *= 1 - discount;
                }
            }
        } else {
            const nonCommonLines = discountedLines.filter(
                (line) => !linesToDiscount.includes(line)
            );
            const discountedAmounts = lines.reduce((map, line) => {
                map[line.get_taxes().map((t) => t.id)];
                return map;
            }, {});
            const process = (line) => {
                const key = line.get_taxes().map((t) => t.id);
                if (!discountedAmounts[key] || line.reward_id) {
                    return;
                }
                const remaining = remainingAmountPerLine[line.cid];
                const consumed = Math.min(remaining, discountedAmounts[key]);
                discountedAmounts[key] -= consumed;
                remainingAmountPerLine[line.cid] -= consumed;
            };
            nonCommonLines.forEach(process);
            commonLines.forEach(process);
        }
    }

    let discountable = 0;
    const discountablePerTax = {};
    let k = [];

    // ── PASS 1: Pre-assign reward_ids to ALL eligible lines ───────────────────
    //
    // calculateRewardShare() (called inside get_unit_price) filters sibling lines
    // by `line.reward_id === this.reward_id`. If we assign reward_ids one-by-one
    // inside a single loop (and call set_discount() in the same iteration),
    // then when line 1 is processed, line 2 still has reward_id=false, so
    // calculateRewardShare() only sees 1 sibling and returns the wrong price.
    //
    // By pre-assigning ALL reward_ids before any set_discount() call, every
    // sibling line is visible to calculateRewardShare() in Pass 2.

    // Determine the effective reward (may downgrade for multi-rule programs)
    let effectiveReward = reward;
    const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
    if (rewardRuleId && reward.program_id.rewards.length > 1) {
        const candidateRewards = reward.program_id.rewards.filter(r => r.ref_loyalty_rule_id);
        if (candidateRewards.length > 0) {
            const satisfiedRewards = candidateRewards.filter(r => {
                const rRuleId = Array.isArray(r.ref_loyalty_rule_id) ? r.ref_loyalty_rule_id[0] : r.ref_loyalty_rule_id;
                const rRule = reward.program_id.rules.find(rule => rule.id === rRuleId);
                return rRule && linesToDiscount.length >= rRule.minimum_qty;
            });
            if (satisfiedRewards.length > 0) {
                satisfiedRewards.sort((a, b) => (b.required_points || 0) - (a.required_points || 0));
                effectiveReward = satisfiedRewards[0];
            }
        }
    } else if (
        reward.buy_with_reward_price === "yes" &&
        reward.program_id.rules.length === 2 &&
        linesToDiscount.length < reward.buy_product_value &&
        reward.program_id.rules.some(rule => rule.minimum_qty === reward.buy_product_value)
    ) {
        const lowerRules = reward.program_id.rules.filter(
            rule => rule.minimum_qty !== reward.buy_product_value
        );
        if (lowerRules.length > 0) {
            const lowerRewards = reward.program_id.rewards.filter(
                r => r.buy_product_value === lowerRules[0].minimum_qty
            );
            if (lowerRewards.length > 0) {
                effectiveReward = lowerRewards[0];
            }
        }
    }

    // Pre-assign reward_id to every line in the eligible set
    for (const line of linesToDiscount) {
        // Reset first so prior state is cleared
        line.promo = effectiveReward.discount;
        line.reward_id = false;

        if (reward.buy_with_reward_price === "yes") {
            // For bundle rewards, only tag lines if minimum qty threshold is met
            const meetsMinQty =
                reward.program_id.rules.length >= 1 &&
                linesToDiscount.length >= (effectiveReward.program_id.rules[0]?.minimum_qty ?? 1);

            if (meetsMinQty) {
                line.reward_id = effectiveReward.id;
            }
        } else {
            // Standard discount: all eligible lines get tagged
            if (!reward.discount_max_amount) {
                line.reward_id = effectiveReward.id;
            }
        }
    }

    // ── PASS 2: Apply discounts now that all reward_ids are set ───────────────
    //
    // At this point every sibling line has reward_id set, so calculateRewardShare()
    // will return the correct per-line price for the full bundle.
    for (const line of linesToDiscount) {
        if (reward.buy_with_reward_price === "yes") {
            // Compute and store the discount VALUE (lot MRP minus reward unit price)
            // so the receipt/display can show how much was saved on this specific lot.
            if (effectiveReward.reward_price > 0 && line.pack_lot_lines) {
                let lotName;
                line.pack_lot_lines.forEach(pack => { lotName = pack.lot_name; });
                const stockLot = this.pos.stock_lots_by_name[lotName];
                if (stockLot && stockLot.stockLot.rs_price > 0) {
                    const lotMrp = line.quantity * stockLot.stockLot.rs_price;
                    const rewardUnitPrice = effectiveReward.reward_price / effectiveReward.buy_product_value;
                    line.set_discount_value(lotMrp - rewardUnitPrice);
                }
            }
            // Apply 0% percentage discount (pricing handled via get_unit_price → calculateRewardShare)
            this._applyDiscountToLine(effectiveReward, line);
        } else {
            // Standard percentage discount
            if (!reward.discount_max_amount) {
                this._applyDiscountToLine(effectiveReward, line);
            } else {
                line.set_discount(0);
                line.set_discount_reward(false);
            }
        }

        // Collect product IDs for return value
        k.push(line.product.nhcl_id);
        console.log(k);

        // Accumulate discountable amounts for tax computation
        discountable += remainingAmountPerLine[line.cid];
        const taxKey = line.get_taxes().map(t => t.id);
        if (!discountablePerTax[taxKey]) {
            discountablePerTax[taxKey] = 0;
        }
        const priceWithTax = line.get_price_with_tax();
        if (priceWithTax) {
            discountablePerTax[taxKey] +=
                line.get_base_price() *
                (remainingAmountPerLine[line.cid] / priceWithTax);
        }
    }
    return { discountable, discountablePerTax, k };
},

//    Pranav Start
    _getDiscountableOnOrder(reward) {
        let discountable = 0;
        const discountablePerTax = {};
        for (const line of this.get_orderlines()) {
            if (!line.get_quantity()) {
                continue;
            }
            const taxKey = ['ewallet', 'gift_card'].includes(reward.program_id.program_type)
                ? line.get_taxes().map((t) => t.id)
                : line.get_taxes().filter((t) => t.amount_type !== 'fixed').map((t) => t.id);
            discountable += line.get_price_with_tax();
            if (!discountablePerTax[taxKey]) {
                discountablePerTax[taxKey] = 0;
            }
            discountablePerTax[taxKey] += line.get_base_price();
        }
        return { discountable, discountablePerTax };
    },
//    Stop

    _getRewardLineValuesDiscount(args) {
        const reward = args["reward"];
        const coupon_id = args["coupon_id"];
        const rewardAppliesTo = reward.discount_applicability;
        let getDiscountable;
        if (rewardAppliesTo === "order") {
            getDiscountable = this._getDiscountableOnOrder.bind(this);
        } else if (rewardAppliesTo === "cheapest") {
            getDiscountable = this._getDiscountableOnCheapest.bind(this);
        } else if (rewardAppliesTo === "specific") {
            getDiscountable = this._getDiscountableOnSpecific.bind(this);
        }
        if (!getDiscountable) {
            return _t("Unknown discount type");
        }
        let { discountable, discountablePerTax, k } = getDiscountable(reward);
        const fix_discount_amount = this.get_orderlines().filter(line => line.is_fix_discount_line)
                .reduce((total, line) => total + (line.price || 0), 0);
        discountable = Math.min(this.get_total_with_tax() - fix_discount_amount, discountable);
        if (!discountable) {
            return [];
        }
        let maxDiscount = reward.discount_max_amount || Infinity;
        if (reward.discount_mode === "per_point") {
            maxDiscount = Math.min(
                maxDiscount,
                reward.discount * this._getRealCouponPoints(coupon_id)
            );
        } else if (reward.discount_mode === "per_order") {
            maxDiscount = Math.min(maxDiscount, reward.discount);
        } else if (reward.discount_mode === "percent") {
            maxDiscount = Math.min(
                maxDiscount,
                discountable * (reward.discount / 100)
            );
        }
        const rewardCode = _newRandomRewardCode();
        let pointCost = reward.clear_wallet
            ? this._getRealCouponPoints(coupon_id)
            : reward.required_points;
        if (reward.discount_mode === "per_point" && !reward.clear_wallet) {
            pointCost = Math.min(maxDiscount, discountable) / reward.discount;
        }
        // These are considered payments and do not require to be either taxed or split by tax
        const discountProduct = reward.discount_line_product_id;
        if (["ewallet", "gift_card"].includes(reward.program_id.program_type)) {
            return [
                {
                    product: discountProduct,
                    price: -Math.min(maxDiscount, discountable),
                    quantity: 1,
                    reward_id: reward.id,
                    is_reward_line: true,
                    coupon_id: coupon_id,
                    points_cost: pointCost,
                    reward_identifier_code: rewardCode,
                    merge: false,
                    tax_ids: [],
                },
            ];
        }
        const discountFactor = discountable
            ? Math.min(1, maxDiscount / discountable)
            : 1;

        if ((reward.discount_applicability === 'specific' || reward.discount_applicability === 'cheapest') && reward.buy_with_reward_price === 'no' && !reward.discount_max_amount) {
            const discountedLines = this.get_orderlines().filter(line => line.reward_id === reward.id);
            discountedLines.forEach((line, index) => {
                line.coupon_id = coupon_id;
                line.reward_identifier_code = rewardCode;
                line.points_cost = index === 0 ? pointCost : 0;
            });
            return [];
        }

        const result = Object.entries(discountablePerTax).reduce(
            (lst, entry) => {
                // Ignore 0 price lines
                if (!entry[1]) {
                    return lst;
                }
//                Pranav Start
                // Ignore discounted price lines
                if (entry[1] < 0) {
                    return lst;
                }
//                Stop
                const taxIds = entry[0] === "" ? [] : entry[0].split(",").map((str) => parseInt(str));
                if (reward.buy_with_reward_price === 'no'){
//                 Pranav Start
                 let price = entry[1] * discountFactor;
//                 if (reward.discount_max_amount && price > reward.discount_max_amount) {
//                    price = reward.discount_max_amount;
//                 }
//                 if (maxDiscount && price > maxDiscount) {
//                    price = maxDiscount;
//                 }
//                 Stop
                 lst.push({
                    product: discountProduct,
                    price: -(price),
                    quantity: 1,
                    reward_id: reward.id,
                    is_reward_line: true,
                    coupon_id: coupon_id,
                    points_cost: 0,
                    reward_identifier_code: rewardCode,
                    tax_ids: taxIds,
                    merge: false,
                    promodisclines: k,
                });
                }

                return lst;
            },
            []
        );

        if (result.length) {
            result[0]["points_cost"] = pointCost;
        }
        return result;
    },

    _getSpecificDiscountableLines(reward) {
        const discountableLines = [];
        const applicableProducts = reward.all_discount_product_ids;
        for (const line of this.get_orderlines()) {
            if (!line.get_quantity()) {
                continue;
            }
            if (
                (applicableProducts.has(line.get_product().id) && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line)) ||
                (line.reward_product_id && applicableProducts.has(line.reward_product_id) && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line))
            ) {
                discountableLines.push(line);
            }
        }
        return discountableLines;
    },

    _getDiscountableOnCheapest(reward) {
        // 1️⃣ Collect serial IDs from rules (if any)
        const program = reward.program_id;
        const serialIds = new Set();

        if (program && program.rules) {
            program.rules.forEach(rule => {
                if (rule.serial_ids) {
                    rule.serial_ids.forEach(id => serialIds.add(id));
                }
            });
        }

        // 2️⃣ Decide eligible lines
        let eligibleLines = this.get_orderlines().filter(line => line.quantity > 0 && !line.refunded_orderline_id);

        // Apply serial filter ONLY if serial rules exist
        if (serialIds.size) {
            eligibleLines = eligibleLines.filter(line => {
                const packLotLines = line.pack_lot_lines;
                if (!packLotLines || !packLotLines.length) {
                    return false;
                }

                let lotId = false;
                packLotLines.forEach(pack => {
                    const stockLot = this.pos.stock_lots_by_name[pack.lot_name];
                    if (stockLot) {
                        lotId = stockLot.stockLot.id;
                    }
                });

                return serialIds.has(lotId);
            });
        }

        // 3️⃣ Sort eligible lines by price ascending
        eligibleLines.sort((a, b) => a.getComboTotalPriceWithoutTax() - b.getComboTotalPriceWithoutTax());

        // 4️⃣ Determine the effective reward (may upgrade/downgrade for multi-rule programs)
        let effectiveReward = reward;
        const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
        const totalEligibleQty = eligibleLines.reduce((sum, line) => sum + line.get_quantity(), 0);

        if (rewardRuleId && reward.program_id.rewards.length > 1) {
            const candidateRewards = reward.program_id.rewards.filter(r => r.ref_loyalty_rule_id);
            if (candidateRewards.length > 0) {
                const satisfiedRewards = candidateRewards.filter(r => {
                    const rRuleId = Array.isArray(r.ref_loyalty_rule_id) ? r.ref_loyalty_rule_id[0] : r.ref_loyalty_rule_id;
                    const rRule = reward.program_id.rules.find(rule => rule.id === rRuleId);
                    return rRule && totalEligibleQty >= rRule.minimum_qty;
                });
                if (satisfiedRewards.length > 0) {
                    satisfiedRewards.sort((a, b) => (b.required_points || 0) - (a.required_points || 0));
                    effectiveReward = satisfiedRewards[0];
                }
            }
        } else {
            // Fallback: check if at least one rule is satisfied
            const activeRule = program.rules.find(rule => totalEligibleQty >= rule.minimum_qty);
            if (!activeRule) {
                return { discountable: 0, discountablePerTax: {} };
            }
        }

        // 5️⃣ Select the cheapest N items (where N = effectiveReward.cheapest_qty || 1)
        const cheapestQtyNeeded = effectiveReward.cheapest_qty || 1;
        const linesToDiscount = [];
        let accumulatedQty = 0;

        for (const line of eligibleLines) {
            if (accumulatedQty >= cheapestQtyNeeded) {
                break;
            }
            const lineQty = line.get_quantity();
            const takeQty = Math.min(lineQty, cheapestQtyNeeded - accumulatedQty);
            linesToDiscount.push({ line, quantity: takeQty });
            accumulatedQty += takeQty;
        }

        if (linesToDiscount.length === 0) {
            return { discountable: 0, discountablePerTax: {} };
        }

        // 6️⃣ If discount_max_amount = 0 (Apply directly to the lines)
        if (!effectiveReward.discount_max_amount) {
            // Reset discount first on all eligible lines to avoid stale discounts
            for (const line of eligibleLines) {
                line.reward_id = false;
                line.promo = 0;
            }

            // Set discount directly on the cheapest lines
            for (const { line, quantity } of linesToDiscount) {
                line.reward_id = effectiveReward.id;
                line.promo = effectiveReward.discount;
                line.set_discount(effectiveReward.discount);
                line.set_discount_reward(effectiveReward.id);
            }

            return {
                discountable: 0,
                discountablePerTax: {},
                k: linesToDiscount.map(x => x.line.id),
            };
        }

        // 7️⃣ If discount_max_amount > 0 (Create a separate discount line)
        let discountable = 0;
        const discountablePerTax = {};

        for (const { line, quantity } of linesToDiscount) {
            const linePriceUnit = line.getComboTotalPriceWithoutTax() / line.get_quantity();
            const portionPrice = linePriceUnit * quantity;
            discountable += portionPrice;

            const taxKey = line.get_taxes().map(t => t.id).join(",");
            if (!discountablePerTax[taxKey]) {
                discountablePerTax[taxKey] = 0;
            }
            discountablePerTax[taxKey] += portionPrice;
        }

        return {
            discountable,
            discountablePerTax,
            k: linesToDiscount.map(x => x.line.id),
        };
    },

    set_orderline_options(line, options) {
        super.set_orderline_options(...arguments);
        if (options && options.is_reward_line) {
            // let orderLines = line.order.get_orderlines();
            // if (orderLines && orderLines[0].gdiscount) {
            //     line.gdiscount = orderLines[0].gdiscount;
            // }
            line.is_reward_line = options.is_reward_line;
            line.reward_id = options.reward_id;
            line.reward_product_id = options.reward_product_id;
            if (line.reward_product_id) {
                const product = this.pos.db.get_product_by_id(
                    line.reward_product_id
                );
                if (product && product.tracking == "serial") {
                    line.quantity = 1;
                }
            }

            line.coupon_id = options.coupon_id;
            line.promodisclines = options.promodisclines;
            line.reward_identifier_code = options.reward_identifier_code;
            line.points_cost = options.points_cost;
            line.price_type = "automatic";
        }
        if (options && options.reward_id) {
            line.reward_id = options.reward_id;
        }
        line.giftBarcode = options.giftBarcode;
        line.giftCardId = options.giftCardId;
        line.eWalletGiftCardProgram = options.eWalletGiftCardProgram;
    },

    _getCmrProgramProductIds(program) {
        if (program._cmrProductIds) {
            return program._cmrProductIds;
        }
        const productIds = new Set();
        if (program.rules) {
            for (const rule of program.rules) {
                if (rule.valid_product_ids) {
                    for (const id of rule.valid_product_ids) {
                        productIds.add(id);
                    }
                }
            }
        }
        if (program.rewards) {
            for (const reward of program.rewards) {
                if (reward.all_discount_product_ids) {
                    for (const id of reward.all_discount_product_ids) {
                        productIds.add(id);
                    }
                }
                if (reward.reward_product_ids) {
                    for (const id of reward.reward_product_ids) {
                        productIds.add(id);
                    }
                }
                if (reward.discount_product_ids) {
                    for (const id of reward.discount_product_ids) {
                        productIds.add(id);
                    }
                }
                if (reward.discount_product_id) {
                    const dpId = Array.isArray(reward.discount_product_id) ? reward.discount_product_id[0] : reward.discount_product_id;
                    if (dpId) {
                        productIds.add(dpId);
                    }
                }
                if (reward.cmr_discount_product_ids) {
                    let rProductIds = [];
                    if (Array.isArray(reward.cmr_discount_product_ids)) {
                        if (typeof reward.cmr_discount_product_ids[0] === "number") {
                            rProductIds = reward.cmr_discount_product_ids;
                        } else if (Array.isArray(reward.cmr_discount_product_ids[0])) {
                            rProductIds = reward.cmr_discount_product_ids[0][2] || [];
                        }
                    }
                    for (const id of rProductIds) {
                        productIds.add(id);
                    }
                }
            }
        }
        program._cmrProductIds = productIds;
        return productIds;
    },

    _cmrLineMatchesRule(rule, line, program) {
        const prodId = line.reward_product_id || line.get_product().id;
        if (!prodId) return false;

        // If the rule has serial restrictions, the line's serial lot must match
        if (rule.serial_ids && rule.serial_ids.size > 0) {
            let lotId = false;
            if (line.pack_lot_lines) {
                let lotName;
                line.pack_lot_lines.forEach(pack => {
                    lotName = pack.lot_name;
                });
                const stockLot = this.pos.stock_lots_by_name[lotName];
                if (stockLot) {
                    lotId = stockLot.stockLot.id;
                }
            }
            if (!lotId || !rule.serial_ids.has(lotId)) {
                return false;
            }
        }

        let matchesProduct = false;
        if (rule.valid_product_ids && rule.valid_product_ids.has(prodId)) {
            matchesProduct = true;
        } else if (rule.any_product) {
            const programProductIds = this._getCmrProgramProductIds(program);
            if (programProductIds.size > 0) {
                matchesProduct = programProductIds.has(prodId);
            } else {
                matchesProduct = true;
            }
        }
        return matchesProduct;
    },
});