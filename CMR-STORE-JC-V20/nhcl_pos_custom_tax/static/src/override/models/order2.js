/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { roundPrecision } from "@web/core/utils/numbers";

let pointsForProgramsCountedRules = {};

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.headerData.terminal = this.pos.config.name;
        result.headerData.cashier_id = this.cashier.barcode_str;
        const company = result.headerData.company;
        result.headerData.company.address = (company.street ? company.street + ", " : "") +
                    (company.zip ? company.zip + ", " : "") +
                    (company.city ? company.city + ", " : "") +
                    (company.state_id ? company.state_id[1] + ", " : "") +
                    (company.country_id ? company.country_id[1] : "")
        result.total_qty = this.orderlines.filter(line => !line.is_reward_line)
                .reduce((total, line) => total + (line.quantity || 0), 0);
        result.credit_ids_list = this.credit_ids_list;
        result.payment_lines = this.paymentlines;
        result.total_gdiscount = result.orderlines.reduce( (sum, line) => sum + line.gdiscount_amount, 0);
        result.total_amount_discount = this.orderlines.filter(line => line.is_fix_discount_line).reduce( (sum, line) => sum + -line.price, 0);
        result.total_line_discount = this.orderlines.filter(line => line.discount_amount && !(line.reward_id || line.is_reward_line || line.discount_reward)).reduce( (sum, line) => sum + line.discount_amount, 0);
        return result;
    },

    /**
     * Update our couponPointChanges, meaning the points/coupons each program give etc.
     */
    async _updatePrograms() {
        const changesPerProgram = {};
        const programsToCheck = new Set();
        // By default include all programs that are considered 'applicable'
        for (const program of this.pos.programs) {
            if (this._programIsApplicable(program)) {
                programsToCheck.add(program.id);
            }
        }
        for (const pe of Object.values(this.couponPointChanges)) {
            if (!changesPerProgram[pe.program_id]) {
                changesPerProgram[pe.program_id] = [];
                programsToCheck.add(pe.program_id);
            }
            changesPerProgram[pe.program_id].push(pe);
        }
        for (const coupon of this.codeActivatedCoupons) {
            programsToCheck.add(coupon.program_id);
        }
        const programs = [...programsToCheck].map((programId) => this.pos.program_by_id[programId]);
        const pointsAddedPerProgram = this.pointsForPrograms(programs);
        for (const program of this.pos.programs) {
            // Future programs may split their points per unit paid (gift cards for example), consider a non applicable program to give no points
            const pointsAdded = this._programIsApplicable(program)
                ? pointsAddedPerProgram[program.id]
                : [];
            // For programs that apply to both (loyalty) we always add a change of 0 points, if there is none, since it makes it easier to
            //  track for claimable rewards, and makes sure to load the partner's loyalty card.
            if (program.is_nominative && !pointsAdded.length && this.get_partner()) {
                pointsAdded.push({ points: 0 });
            }
            const oldChanges = changesPerProgram[program.id] || [];
            // Update point changes for those that exist
            for (let idx = 0; idx < Math.min(pointsAdded.length, oldChanges.length); idx++) {
                Object.assign(oldChanges[idx], pointsAdded[idx]);
                oldChanges[idx].appliedRules = pointsForProgramsCountedRules[program.id] || [];
            }
            if (pointsAdded.length < oldChanges.length) {
                const removedIds = oldChanges.map((pe) => pe.coupon_id);
                this.couponPointChanges = Object.fromEntries(
                    Object.entries(this.couponPointChanges).filter(([k, pe]) => {
                        return !removedIds.includes(pe.coupon_id);
                    })
                );
            } else if (pointsAdded.length > oldChanges.length) {
                for (const pa of pointsAdded.splice(oldChanges.length)) {
                    const coupon = await this._couponForProgram(program);
                    this.couponPointChanges[coupon.id] = {
                        points: pa.points,
                        program_id: program.id,
                        coupon_id: coupon.id,
                        barcode: pa.barcode,
                        appliedRules: pointsForProgramsCountedRules[program.id],
                        giftCardId: pa.giftCardId
                    };
                }
            }
        }
        // Also remove coupons from codeActivatedCoupons if their program applies_on current orders and the program does not give any points
        this.codeActivatedCoupons = this.codeActivatedCoupons.filter((coupon) => {
            const program = this.pos.program_by_id[coupon.program_id];
            if (
                program.applies_on === "current" &&
                pointsAddedPerProgram[program.id].length === 0
            ) {
                return false;
            }
            return true;
        });
    },

    /**
     * Computes how much points each program gives.
     *
     * @param {Array} programs list of loyalty.program
     * @returns {Object} Containing the points gained per program
     */
    pointsForPrograms(programs, getwithrule = false) {
        pointsForProgramsCountedRules = {};
        const orderLines = this.get_orderlines().filter((line) => !line.refunded_orderline_id);
        const linesPerRule = {};
        for (const line of orderLines) {
            for (const program of programs) {
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
            let appliedRule = null; // Track the rule for "order" or global modes
            const splitPoints = [];

            for (const rule of program.rules) {
                if (rule.mode === "with_code" && !this.codeActivatedProgramRules.includes(rule.id)) {
                    continue;
                }
                const linesForRule = linesPerRule[rule.id] ? linesPerRule[rule.id] : [];
                const amountWithTax = linesForRule.reduce((sum, line) => sum + line.get_price_with_tax(), 0);
                const amountWithoutTax = linesForRule.reduce((sum, line) => sum + line.get_price_without_tax(), 0);
                var amountCheck = (rule.minimum_amount_tax_mode === "incl" && amountWithTax) || amountWithoutTax;

                // // For considering Fix Amount discount on total to check with minimum_amount condition
                // const fix_discount_lines = orderLines.filter((line) => line.is_fix_discount_line);
                // if (fix_discount_lines.length > 0) {
                //     amountCheck += fix_discount_lines[0].get_price_with_tax();
                // }

                if (rule.minimum_amount > amountCheck) {
                    continue;
                }

                let totalProductQty = 0;
                const qtyPerProduct = {};
                let orderedProductPaid = 0;

                for (const line of orderLines) {
                    if (this._cmrLineMatchesRule(rule, line, program) &&
                        !line.ignoreLoyaltyPoints({ program })) {

                        if (line.is_reward_line) {
                            const reward = this.pos.reward_by_id[line.reward_id];
                            if (reward && reward.program_id && ((program.id === reward.program_id.id) || ['gift_card', 'ewallet'].includes(reward.program_id.program_type))) {
                                continue;
                            }
                        }

                        const lineQty = line.reward_product_id ? -line.get_quantity() : line.get_quantity();
                        const prodId = line.reward_product_id || line.get_product().id;
                        qtyPerProduct[prodId] = (qtyPerProduct[prodId] || 0) + lineQty;
                        orderedProductPaid += line.get_price_with_tax();

                        if (!line.is_reward_line) {
                            totalProductQty += lineQty;
                        }
                    }
                }

                if (totalProductQty < rule.minimum_qty) {
                    continue;
                }

                if (!(program.id in pointsForProgramsCountedRules)) {
                    pointsForProgramsCountedRules[program.id] = [];
                }
                pointsForProgramsCountedRules[program.id].push(rule.id);

                if (program.applies_on === "future" && rule.reward_point_split && rule.reward_point_mode !== "order") {
                    if (rule.reward_point_mode === "unit") {
                        splitPoints.push(...Array.from({ length: totalProductQty }, () => ({
                            points: rule.reward_point_amount,
                            ...(getwithrule ? { rule } : {}) // Add rule if requested
                        })));
                    } else if (rule.reward_point_mode === "money") {
                        for (const line of orderLines) {
                            if (line.is_reward_line || !rule.valid_product_ids.has(line.get_product().id) || line.get_quantity() <= 0 || line.ignoreLoyaltyPoints({ program })) {
                                continue;
                            }
                            const pointsPerUnit = roundPrecision((rule.reward_point_amount * line.get_price_with_tax()) / line.get_quantity(), 0.01);
                            if (pointsPerUnit > 0) {
                                splitPoints.push(...Array.from({ length: line.get_quantity() }, () => ({
                                    points: pointsPerUnit,
                                    barcode: line.giftBarcode,
                                    giftCardId: line.giftCardId,
                                    ...(getwithrule ? { rule } : {}) // Add rule if requested
                                })));
                            }
                        }
                    }
                } else {
                    appliedRule = rule; // Store the rule that generated the points
                    if (rule.reward_point_mode === "order") {
                        points += rule.reward_point_amount;
                    } else if (rule.reward_point_mode === "money") {
                        points += roundPrecision(rule.reward_point_amount * orderedProductPaid, 0.01);
                    } else if (rule.reward_point_mode === "unit") {
                        points += rule.reward_point_amount * totalProductQty;
                    }
                }
            }

            // Final result construction
            const mainPointObj = { points };
            if (getwithrule && appliedRule) {
                mainPointObj.rule = appliedRule;
            }

            const res = points || program.program_type === "coupons" ? [mainPointObj] : [];
            if (splitPoints.length) {
                res.push(...splitPoints);
            }
            result[program.id] = res;
        }
        return result;
    },

    /**
     * @returns {Array} List of lines composing the global discount
     */
    _getGlobalDiscountLines() {
        return this.get_orderlines().filter(
            (line) => line.reward_id && this.pos.reward_by_id[line.reward_id] && this.pos.reward_by_id[line.reward_id].is_global_discount
        );
    },

    /**
     * Refreshes the currently applied rewards, if they are not applicable anymore they are removed.
     */
    _updateRewardLines() {
        if (!this.orderlines.length) {
            return;
        }
        const rewardLines = this._get_reward_lines();
        if (!rewardLines.length) {
            return;
        }
        const productRewards = [];
        const otherRewards = [];
        const paymentRewards = []; // Gift card and ewallet rewards are considered payments and must stay at the end
        for (const line of rewardLines) {
            const claimedReward = {
                reward: this.pos.reward_by_id[line.reward_id],
                coupon_id: line.coupon_id,
                args: {
                    product: line.reward_product_id,
                    price: line.price,
                    quantity: line.quantity,
                    cost: line.points_cost,
                },
                reward_identifier_code: line.reward_identifier_code,
            };
            if (claimedReward.reward) {
                if (
                    claimedReward.reward.program_id.program_type === "gift_card" ||
                    claimedReward.reward.program_id.program_type === "ewallet"
                ) {
                    paymentRewards.push(claimedReward);
                } else if (claimedReward.reward.reward_type === "product") {
                    productRewards.push(claimedReward);
                } else if (
                    !otherRewards.some(
                        (reward) =>
                            reward.reward_identifier_code === claimedReward.reward_identifier_code
                    )
                ) {
                    otherRewards.push(claimedReward);
                }
            }
            this.orderlines.remove(line);
        }
        const allRewards = productRewards.concat(otherRewards).concat(paymentRewards);
        const allRewardsMerged = [];
        allRewards.forEach((reward) => {
            if (reward.reward.reward_type == "discount") {
                allRewardsMerged.push(reward);
            } else {
                const reward_index = allRewardsMerged.findIndex(
                    (item) =>
                        item.reward.id === reward.reward.id && item.args.price === reward.args.price
                );
                if (reward_index > -1) {
                    allRewardsMerged[reward_index].args.quantity += reward.args.quantity;
                    allRewardsMerged[reward_index].args.cost += reward.args.cost;
                } else {
                    allRewardsMerged.push(reward);
                }
            }
        });

        for (const claimedReward of allRewardsMerged) {
            // For existing coupons check that they are still claimed, they can exist in either `couponPointChanges` or `codeActivatedCoupons`
            if (
                !this.codeActivatedCoupons.find(
                    (coupon) => coupon.id === claimedReward.coupon_id
                ) &&
                !this.couponPointChanges[claimedReward.coupon_id]
            ) {
                continue;
            }
            this._applyReward(claimedReward.reward, claimedReward.coupon_id, claimedReward.args);
        }
    },

});
