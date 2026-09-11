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

    },

    _programIsApplicable(program) {
        if (program.is_active === false) {
            return false;
        }
        if (!program.rules || program.rules.length === 0) {
            return false;
        }
        const hasSerialOrGrcRule = program.rules.some(rule => {
            const isSerialOrGrc = ['serial', 'grc', 'filter'].includes(rule.type_filter);
            const hasSerials = rule.serial_ids && (rule.serial_ids instanceof Set ? rule.serial_ids.size > 0 : rule.serial_ids.length > 0);
            return isSerialOrGrc || hasSerials;
        });
        if (hasSerialOrGrcRule) {
            return true;
        }
        return super._programIsApplicable(...arguments);
    },

    getTotalWithTaxBeforeGlobal() {
        return this.get_orderlines().reduce((sum, line) => {
            if (line.is_reward_line || line.is_fix_discount_line) {
                return sum + line.get_price_with_tax();
            }
            const prices = line.get_all_prices();
            const gdiscount = parseFloat(line.get_gdiscount()) || 0;
            const priceWithTax = prices.priceWithTax;
            if (gdiscount > 0 && gdiscount < 100) {
                return sum + (priceWithTax / (1 - gdiscount / 100));
            }
            return sum + priceWithTax;
        }, 0);
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
            pointsForProgramsCountedRules = {};
            const orderLines = this.get_orderlines().filter((line) => !line.refunded_orderline_id);
            const linesPerRule = {};
            for (const line of orderLines) {
                const reward = line.reward_id ? this.pos.reward_by_id[line.reward_id] : undefined;
                const isDiscount = reward && reward.reward_type === "discount";
                const rewardProgram = reward && reward.program_id;
                if (isDiscount && rewardProgram && rewardProgram.trigger === "auto") {
                    continue;
                }
                for (const program of programs) {
                    if (isDiscount && rewardProgram && rewardProgram.id === program.id) {
                        continue;
                    }
                    for (const rule of program.rules) {
                        if (this._cmrLineMatchesRule(rule, line, program)) {
                            if (!linesPerRule[rule.id]) {
                                linesPerRule[rule.id] = [];
                            }
                            linesPerRule[rule.id].push(line);
                        }
                    }
                }
            }
            const result = {};
            for (const program of programs) {
                let points = 0;
                const splitPoints = [];
                for (const rule of program.rules) {
                    if (
                        rule.mode === "with_code" &&
                        !this.codeActivatedProgramRules.includes(rule.id)
                    ) {
                        continue;
                    }
                    const linesForRule = linesPerRule[rule.id] ? linesPerRule[rule.id] : [];
                    const useTax = rule.minimum_amount_tax_mode === "incl";
                    const amountWithTax = linesForRule.reduce(
                        (sum, line) => sum + line.get_price_with_tax_before_discount(),
                        0
                    );
                    const amountWithoutTax = linesForRule.reduce(
                        (sum, line) => sum + line.get_price_without_tax_before_discount(),
                        0
                    );
                    const qty = linesForRule.reduce((sum, line) => sum + line.get_quantity(), 0);
                    if (qty < rule.minimum_qty) {
                        continue;
                    }
                    const amount = useTax ? amountWithTax : amountWithoutTax;
                    if (amount < rule.minimum_amount) {
                        continue;
                    }
                    let pointsAdded = 0;
                    if (rule.reward_point_mode === "order") {
                        pointsAdded = rule.reward_point_amount;
                    } else if (rule.reward_point_mode === "money") {
                        pointsAdded = roundPrecision(rule.reward_point_amount * amount, 0.01);
                    } else if (rule.reward_point_mode === "unit") {
                        pointsAdded = rule.reward_point_amount * qty;
                    }
                    points += pointsAdded;

                    if (rule.reward_point_mode === "unit" && program.applies_on === "future") {
                        for (const line of linesForRule) {
                            for (let i = 0; i < line.get_quantity(); i++) {
                                splitPoints.push({
                                    points: rule.reward_point_amount,
                                    barcode: line.giftBarcode,
                                    giftCardId: line.giftCardId,
                                });
                            }
                        }
                    }
                }
                result[program.id] = splitPoints.length ? splitPoints : [{ points }];
            }
            return result;
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

    async activateCode(code) {
        this.block_auto_promotions = false;
        return super.activateCode(...arguments);
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.credit_ids = this.credit_ids || [];
        json.credit_note_amounts = this.credit_note_amounts || [];
        json.credit_id = this.credit_id || 0;
        json.block_auto_promotions = this.block_auto_promotions || false;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.credit_ids = json.credit_ids || [];
        this.credit_note_amounts = json.credit_note_amounts || [];
        this.credit_id = json.credit_id || 0;
        this.block_auto_promotions = json.block_auto_promotions || false;
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
    _getLotIdFromLine(line) {
        if (!line || !line.pack_lot_lines || !line.pack_lot_lines.length) {
            return false;
        }
        for (const pack of line.pack_lot_lines) {
            if (!pack.lot_name) continue;
            const key = pack.lot_name.trim();
            const stockLotObj = this.pos.stock_lots_by_name?.[key]?.stockLot;
            if (stockLotObj && stockLotObj.id) {
                return stockLotObj.id;
            }
            const keyUpper = key.toUpperCase();
            for (const k in (this.pos.stock_lots_by_name || {})) {
                if (k.toUpperCase() === keyUpper) {
                    const lot = this.pos.stock_lots_by_name[k]?.stockLot;
                    if (lot && lot.id) {
                        return lot.id;
                    }
                }
            }
        }
        return false;
    },

    async _updateRewards() {
        if (this._updatingRewardsInProgress) {
            return;
        }
        this._updatingRewardsInProgress = true;
        try {
            await super._updateRewards(...arguments);
        } finally {
            this._updatingRewardsInProgress = false;
        }
    },

    _isRewardProductPartOfRuleSerial(reward, applicableProducts, currentline) {
        const lotId = this._getLotIdFromLine(currentline);

        // If the reward specifies stock_lot_ids, currentline's lot MUST match
        if (reward.stock_lot_ids && reward.stock_lot_ids.size > 0) {
            if (!lotId || !reward.stock_lot_ids.has(lotId)) {
                return false;
            }
        }

        // Evaluate whether the program rules (BUY condition) are satisfied across the cart
        const program = reward.program_id;
        if (!program || !program.rules || program.rules.length === 0) {
            return true;
        }

        // If a rule specifies serial_ids, currentline's lot MUST match rule.serial_ids
        const ruleWithSerials = program.rules.find(r => r.serial_ids && r.serial_ids.size > 0);
        if (ruleWithSerials) {
            if (!lotId || !ruleWithSerials.serial_ids.has(lotId)) {
                return false;
            }
        }

        const meetsThreshold = program.rules.some(rule => {
            const useTax = rule.minimum_amount_tax_mode === "incl";
            let ruleQty = 0;
            let ruleValue = 0;

            for (const line of this.orderlines) {
                if (line.refunded_orderline_id) continue;

                // Check rule serial constraint if present
                if (rule.serial_ids && rule.serial_ids.size > 0) {
                    const lineLotId = this._getLotIdFromLine(line);
                    if (!lineLotId || !rule.serial_ids.has(lineLotId)) {
                        continue;
                    }
                }

                if (this._cmrLineMatchesRule(rule, line, program)) {
                    ruleQty += line.get_quantity();
                    ruleValue += useTax ? line.get_price_with_tax_before_discount() : line.get_price_without_tax_before_discount();
                }
            }

            return ruleQty >= rule.minimum_qty && ruleValue >= rule.minimum_amount;
        });

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

    removeProgramRewards(programId) {
        if (!programId) return;
        const lines = [...(this.get_orderlines() || [])];
        for (const line of lines) {
            const rid = line.reward_id || line.discount_reward;
            const r = rid ? this.pos.reward_by_id?.[rid] : null;
            if (r?.program_id?.id === programId) {
                if (line.is_reward_line || line.reward_product_id) {
                    this._unlinkOrderline(line);
                } else {
                    line.reward_id = false;
                    line.set_discount(0);
                    if (typeof line.set_discount_reward === "function") {
                        line.set_discount_reward(false);
                    }
                    line.coupon_id = null;
                    line.points_cost = 0;
                    line.reward_identifier_code = null;
                }
            }
        }
    },

    _isRuleSatisfied(rule, program) {
        if (!rule) return true;
        const orderLines = this.get_orderlines().filter((line) => !line.refunded_orderline_id);
        const linesForRule = orderLines.filter((line) => this._cmrLineMatchesRule(rule, line, program));
        if (!linesForRule.length) return false;

        const useTax = rule.minimum_amount_tax_mode === "incl";
        const amount = linesForRule.reduce(
            (sum, line) => sum + (useTax ? line.get_price_with_tax_before_discount() : line.get_price_without_tax_before_discount()),
            0
        );
        const qty = linesForRule.reduce((sum, line) => sum + line.get_quantity(), 0);

        if (rule.minimum_amount > 0 && amount < rule.minimum_amount) {
            return false;
        }
        if (rule.minimum_qty > 0 && qty < rule.minimum_qty) {
            return false;
        }
        return true;
    },

    getClaimableRewards(coupon_id = false, program_id = false, auto = false) {
        if (this.block_auto_promotions && auto) {
            return [];
        }
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

            const programIdsInCoupons = new Set(allCouponPrograms.map((cp) => cp.program_id));
            for (const program of this.pos.programs) {
                if (!programIdsInCoupons.has(program.id) && this._programIsApplicable(program)) {
                    allCouponPrograms.push({
                        program_id: program.id,
                        coupon_id: 0,
                    });
                }
            }

            const result = [];
            const totalWithTax = this.get_total_with_tax();
            const totalWithoutTax = this.get_total_without_tax();
            const totalIsZero = totalWithTax === 0;

            const globalDiscountLines = this._getGlobalDiscountLines();
            const globalDiscountPercent = globalDiscountLines.length
                ? this.pos.reward_by_id[globalDiscountLines[0].reward_id].discount
                : 0;

            for (const couponProgram of allCouponPrograms) {
                const program = this.pos.program_by_id[couponProgram.program_id];
                if (!program) continue;

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

                let points = 0;
                if (couponProgram.coupon_id && couponProgram.coupon_id > 0) {
                    points = this._getRealCouponPoints(couponProgram.coupon_id);
                } else {
                    const pointsDict = this.pointsForPrograms([program]);
                    const ptsList = pointsDict[program.id] || [];
                    points = ptsList.reduce((sum, p) => sum + (p.points || 0), 0);
                }

                for (let rewardIdx = 0; rewardIdx < program.rewards.length; rewardIdx++) {
                    const reward = program.rewards[rewardIdx];

                    const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
                    let targetRule = null;
                    if (rewardRuleId) {
                        targetRule = program.rules.find(r => r.id === rewardRuleId);
                    } else if (program.rules && program.rules.length > 0) {
                        targetRule = program.rules[rewardIdx] || program.rules[0];
                    }

                    if (targetRule && !this._isRuleSatisfied(targetRule, program)) {
                        continue;
                    }

                    if (reward.required_points > 0 && points < reward.required_points) {
                        continue;
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

                    let unclaimedQty = 1;
                    if (reward.reward_type === "product") {
                        if (!reward.multi_product) {
                            const product = this.pos.db.get_product_by_id(
                                reward.reward_product_ids[0]
                            );
                            if (product) {
                                try {
                                    if (couponProgram.coupon_id && this.couponPointChanges && this.couponPointChanges[couponProgram.coupon_id]) {
                                        unclaimedQty = this._computeUnclaimedFreeProductQty(
                                            reward,
                                            couponProgram.coupon_id,
                                            product,
                                            points
                                        );
                                    } else {
                                        unclaimedQty = reward.reward_product_qty || 1;
                                    }
                                } catch (e) {
                                    unclaimedQty = reward.reward_product_qty || 1;
                                }
                            }
                        }
                        if (!unclaimedQty || unclaimedQty <= 0) {
                            unclaimedQty = reward.reward_product_qty || 1;
                        }
                    }

                    result.push({
                        coupon_id: couponProgram.coupon_id,
                        reward: reward,
                        potentialQty: unclaimedQty,
                    });
                }
            }

            // Filter result per program to return ONLY the reward for the latest (highest threshold) satisfied rule
            const filteredResult = [];
            const programResultMap = new Map();

            for (const item of result) {
                const programId = item.reward?.program_id?.id;
                if (!programId) {
                    filteredResult.push(item);
                    continue;
                }
                if (!programResultMap.has(programId)) {
                    programResultMap.set(programId, []);
                }
                programResultMap.get(programId).push(item);
            }

            for (const [programId, items] of programResultMap.entries()) {
                if (items.length <= 1) {
                    filteredResult.push(...items);
                    continue;
                }
                const program = items[0].reward.program_id;
                const rules = program?.rules || [];
                let maxMinAmount = -1;
                let bestItem = items[0];

                for (const item of items) {
                    const reward = item.reward;
                    const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
                    let targetRule = null;
                    if (rewardRuleId && rules.length > 0) {
                        targetRule = rules.find(r => r.id === rewardRuleId);
                    } else if (rules.length > 0) {
                        const rIdx = (program.rewards || []).indexOf(reward);
                        targetRule = (rIdx >= 0 && rules[rIdx]) ? rules[rIdx] : rules[0];
                    }
                    const minAmt = targetRule ? (targetRule.minimum_amount || 0) : (reward.minimum_amount || 0);
                    if (minAmt >= maxMinAmount) {
                        maxMinAmount = minAmt;
                        bestItem = item;
                    }
                }
                filteredResult.push(bestItem);
            }

            return filteredResult;
        }
        return [];
    },

    removeOrderline(line) {
        const linesToRemove = line.getAllLinesInCombo();
        for (const lineToRemove of linesToRemove) {
            this._unlinkOrderline(lineToRemove);
            if (lineToRemove.reward_id) {
                const reward = this.pos.reward_by_id[lineToRemove.reward_id];
                if (reward.buy_with_reward_price === "yes") {
                    if (reward.program_id.rules.length == 1) {
                        this._getRewardLineValues({
                            reward: reward,

                        });
                    }
                    else if (reward.program_id.rules.length === 2 && (reward.program_id.rewards.filter(
                        (reward_id) => reward_id.required_points === reward.buy_product_value
                    )).length > 0) {
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

        const hasRewardSerials = reward.stock_lot_ids && reward.stock_lot_ids.size > 0;
        const hasRuleSerials = reward.program_id && reward.program_id.rules && reward.program_id.rules.some(r => r.serial_ids && r.serial_ids.size > 0);
        const isSerialBased = hasRewardSerials || hasRuleSerials;

        for (const line of orderLines) {
            if (!line.get_quantity() || !line.price) {
                continue;
            }
            remainingAmountPerLine[line.cid] = line.get_price_with_tax_before_discount();

            let isEligible = false;
            if (isSerialBased) {
                isEligible = this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line);
            } else {
                const productIsApplicable = applicableProducts.has(line.get_product().id);
                const isApplicableRewardLine = line.reward_product_id && applicableProducts.has(line.reward_product_id);
                isEligible = (productIsApplicable || isApplicableRewardLine) && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line);
            }

            if (isEligible) {
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
            const lineReward = lines[0] && lines[0].reward_id ? this.pos.reward_by_id[lines[0].reward_id] : null;
            if (!lineReward || lineReward.reward_type !== "discount") {
                continue;
            }
            let discountedLines = orderLines;
            if (lineReward.discount_applicability === "cheapest") {
                cheapestLine = cheapestLine || this._getCheapestLine(lineReward);
                discountedLines = [cheapestLine].filter(Boolean);
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
        const k = [];

        for (const line of linesToDiscount) {
            k.push(line.product.nhcl_id);
            discountable += remainingAmountPerLine[line.cid];
            const taxKey = line.get_taxes().map(t => t.id).join(",");
            if (!discountablePerTax[taxKey]) {
                discountablePerTax[taxKey] = 0;
            }
            const priceWithTax = line.get_price_with_tax_before_discount();
            if (priceWithTax) {
                const basePrice = line.get_price_without_tax_before_discount ? line.get_price_without_tax_before_discount() : line.get_price_without_tax();
                discountablePerTax[taxKey] += basePrice * (remainingAmountPerLine[line.cid] / priceWithTax);
            }
        }
        return { discountable, discountablePerTax, k };
    },

    //    Pranav Start
    _getDiscountableOnOrder(reward) {
        let discountable = 0;
        const discountablePerTax = {};
        const eligibleLines = this.get_orderlines().filter(line =>
            line.get_quantity() > 0 &&
            !line.is_reward_line &&
            !line.is_fix_discount_line &&
            (!line.reward_id || line.reward_id === reward.id)
        );
        for (const line of eligibleLines) {
            const taxKey = ['ewallet', 'gift_card'].includes(reward.program_id.program_type)
                ? line.get_taxes().map((t) => t.id)
                : line.get_taxes().filter((t) => t.amount_type !== 'fixed').map((t) => t.id);
            discountable += line.get_unit_price() * line.get_quantity();
            if (!discountablePerTax[taxKey]) {
                discountablePerTax[taxKey] = 0;
            }
            discountablePerTax[taxKey] += line.get_base_price();
            line.reward_id = reward.id;
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
        discountable = Math.min(this.getTotalWithTaxBeforeGlobal() - fix_discount_amount, discountable);
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

        let discountedLines = [];
        if (reward.discount_applicability === "specific") {
            discountedLines = this._getSpecificDiscountableLines(reward);
        } else if (reward.discount_applicability === "cheapest") {
            const cheapest = this._getCheapestLine(reward);
            if (cheapest) discountedLines = [cheapest];
        } else {
            discountedLines = this.get_orderlines().filter(
                (line) => !line.is_reward_line && !line.refunded_orderline_id
            );
        }

        let discountPercent = reward.discount;
        if (reward.buy_with_reward_price === 'yes' && reward.reward_price !== undefined) {
            const bundleSize = reward.buy_product_value || 1;
            if (discountedLines.length >= bundleSize) {
                const bundleMultiplier = Math.floor(discountedLines.length / bundleSize);
                const activeCount = bundleMultiplier * bundleSize;
                discountedLines = discountedLines.slice(0, activeCount);
                const targetTotalPrice = reward.reward_price * bundleMultiplier;
                const totalOriginalPrice = discountedLines.reduce((sum, line) => {
                    const base = line.get_price_with_tax_before_discount ? line.get_price_with_tax_before_discount() : line.get_price_with_tax();
                    return sum + (base || 0);
                }, 0);
                if (totalOriginalPrice > targetTotalPrice && totalOriginalPrice > 0) {
                    discountPercent = (1 - (targetTotalPrice / totalOriginalPrice)) * 100;
                } else {
                    discountPercent = 0;
                }
            } else {
                discountPercent = 0;
            }
        } else if (reward.discount_mode === "percent") {
            let maxDiscountAmount = reward.discount_max_amount || Infinity;
            const uncappedAmount = discountable * (reward.discount / 100);
            if (uncappedAmount > maxDiscountAmount && discountable > 0) {
                discountPercent = (maxDiscountAmount / discountable) * 100;
            } else {
                discountPercent = reward.discount;
            }
        } else if (reward.discount_mode === "per_order" || reward.discount_mode === "per_point") {
            const effectiveDiscountAmount = Math.min(maxDiscount, discountable);
            discountPercent = discountable > 0 ? (effectiveDiscountAmount / discountable) * 100 : reward.discount;
        }

        discountedLines.forEach((line, index) => {
            if (line.reward_id && line.reward_id !== reward.id) {
                const existingReward = this.pos.reward_by_id[line.reward_id];
                if (existingReward && (existingReward.discount || 0) >= (reward.discount || 0)) {
                    return;
                }
            }
            line.reward_id = reward.id;
            line.coupon_id = coupon_id;
            line.reward_identifier_code = rewardCode;
            line.points_cost = index === 0 ? pointCost : 0;
            line.set_discount(reward.buy_with_reward_price === 'yes' ? 0 : discountPercent);
            line.set_discount_reward(reward.id);
        });
        return [];

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
                if (reward.buy_with_reward_price === 'no') {
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
        const hasRewardSerials = reward.stock_lot_ids && reward.stock_lot_ids.size > 0;
        const hasRuleSerials = reward.program_id && reward.program_id.rules && reward.program_id.rules.some(r => r.serial_ids && r.serial_ids.size > 0);
        const isSerialBased = hasRewardSerials || hasRuleSerials;

        for (const line of this.get_orderlines()) {
            if (!line.get_quantity()) {
                continue;
            }
            if (isSerialBased) {
                if (this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line)) {
                    discountableLines.push(line);
                }
            } else {
                if (
                    (applicableProducts.has(line.get_product().id) && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line)) ||
                    (line.reward_product_id && applicableProducts.has(line.reward_product_id) && this._isRewardProductPartOfRuleSerial(reward, applicableProducts, line))
                ) {
                    discountableLines.push(line);
                }
            }
        }
        return discountableLines;
    },

    _getCheapestLine(reward = false) {
        let eligibleLines = this.get_orderlines().filter(
            (line) => !line.is_reward_line && !line.refunded_orderline_id && line.quantity > 0
        );

        if (reward) {
            const specificLines = this._getSpecificDiscountableLines(reward);
            if (specificLines.length > 0) {
                eligibleLines = eligibleLines.filter((line) => specificLines.includes(line));
            } else {
                return null;
            }
        }

        if (!eligibleLines.length) {
            return null;
        }

        return eligibleLines.reduce((cheapest, line) => {
            if (!cheapest || line.price < cheapest.price) {
                return line;
            }
            return cheapest;
        }, null);
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
                const lotId = this._getLotIdFromLine(line);
                return lotId && serialIds.has(lotId);
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

        // Reset discount first on all eligible lines to avoid stale discounts
        for (const line of eligibleLines) {
            line.reward_id = false;
            line.promo = 0;
        }

        // Tag the cheapest lines with reward_id
        for (const { line, quantity } of linesToDiscount) {
            line.reward_id = effectiveReward.id;
            line.promo = effectiveReward.discount;
        }

        let discountable = 0;
        const discountablePerTax = {};

        for (const { line, quantity } of linesToDiscount) {
            const linePriceUnit = line.get_unit_price();
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
                if (reward.stock_lot_ids && reward.stock_lot_ids.size > 0) {
                    for (const lotId of reward.stock_lot_ids) {
                        for (const name in this.pos.stock_lots_by_name) {
                            const lotObj = this.pos.stock_lots_by_name[name]?.stockLot;
                            if (lotObj && lotObj.id === lotId && lotObj.product_id) {
                                productIds.add(lotObj.product_id[0]);
                            }
                        }
                    }
                }
            }
        }
        program._cmrProductIds = productIds;
        return productIds;
    },

    _cmrLineMatchesRule(rule, line, program) {
        if (line.is_reward_line) {
            return false;
        }
        // If the rule has serial restrictions, match strictly by serial_ids ONLY (do NOT check product)
        if (rule.serial_ids && rule.serial_ids.size > 0) {
            const lotId = this._getLotIdFromLine(line);
            return !!(lotId && rule.serial_ids.has(lotId));
        }

        const prodId = line.reward_product_id || line.get_product().id;
        if (!prodId) return false;

        if (rule.valid_product_ids && rule.valid_product_ids.size > 0 && rule.valid_product_ids.has(prodId)) {
            return true;
        }
        if (rule.product_category_id) {
            const catId = Array.isArray(rule.product_category_id) ? rule.product_category_id[0] : (rule.product_category_id.id || rule.product_category_id);
            const lineProd = line.get_product();
            if (lineProd && lineProd.categ_id && (lineProd.categ_id === catId || lineProd.categ_id[0] === catId)) {
                return true;
            }
        }
        if (rule.any_product) {
            return true;
        }
        return false;
    },
});