/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order, Orderline } from "@point_of_sale/app/store/models";

// ------- toggles -------
const AUTO_APPLY_PRODUCT_REWARDS = false; // true if you also want free-product rewards

// ------- capture originals SAFELY (may be undefined depending on load order) -------
const _origAddProduct = typeof Order.prototype.add_product === "function" ? Order.prototype.add_product : null;
const _origRemoveOrderline = typeof Order.prototype.remove_orderline === "function" ? Order.prototype.remove_orderline : null;
const _origSetPartner = typeof Order.prototype.set_partner === "function" ? Order.prototype.set_partner : null;
const _origSetPricelist = typeof Order.prototype.set_pricelist === "function" ? Order.prototype.set_pricelist : null;

const _origSetQuantity = typeof Orderline.prototype.set_quantity === "function" ? Orderline.prototype.set_quantity : null;
const _origSetUnitPrice = typeof Orderline.prototype.set_unit_price === "function" ? Orderline.prototype.set_unit_price : null;
const _origSetDiscount = typeof Orderline.prototype.set_discount === "function" ? Orderline.prototype.set_discount : null;
const _origSetPackLotLines = typeof Orderline.prototype.setPackLotLines === "function" ? Orderline.prototype.setPackLotLines : null;

// ------- helpers -------
const EPS = 0.01;

function _groupBy(arr, keyFn) {
    const m = {};
    for (const x of arr || []) {
        const k = keyFn(x);
        if (k == null) continue;
        (m[k] ||= []).push(x);
    }
    return m;
}

function _appliedProgramIds(order) {
    const ids = new Set();
    for (const line of order.get_orderlines() || []) {
        if (!line.is_reward_line) continue;
        const r = order.pos.reward_by_id?.[line.reward_id];
        const pid = r?.program_id?.id;
        if (pid) ids.add(pid);
    }
    return ids;
}

function _currentProgramDiscount(order, programId) {
    let total = 0;
    for (const line of order.get_orderlines() || []) {
        if (!line.is_reward_line) continue;
        const r = order.pos.reward_by_id?.[line.reward_id];
        if (r?.program_id?.id === programId) {
            total += Math.abs(line.get_display_price() * line.get_quantity());
        }
    }
    return total;
}

function _orderBaseAmount(order) {
    const lines = (order.get_orderlines() || []).filter(
        (l) => !l.is_reward_line && !l.display_is_total_discount
    );
    return lines.reduce((s, l) => s + l.get_price_with_tax() * l.get_quantity(), 0);
}

function _estimateIntended(reward, base) {
    if (reward.reward_type === "discount") return AUTO_APPLY_PRODUCT_REWARDS ? 1 : 0;
    return reward.discount_mode === "percentage"
        ? ((reward.discount ?? 0) / 100) * base
        : (reward.discount ?? 0);
}

function _getClaimables(order) {
    console.log("==============> ", order);
    const claimable = order.getClaimableRewards ? order.getClaimableRewards() : [];
    // exclude eWallet programs
    if (claimable) {
        return claimable.filter(({ reward }) => reward?.program_id?.program_type !== "ewallet");
    }
    return;
}

// SAFE line removal: no recursion, no missing original
function _safeRemoveLine(order, line) {
    // Prefer low-level collection remove to avoid calling our own wrapper
    if (order?.orderlines?.remove) {
        order.orderlines.remove(line);
        return;
    }
    // Fallback to original remove if it exists
    if (_origRemoveOrderline) {
        _origRemoveOrderline.call(order, line);
        return;
    }
    // Last resort: set qty to 0
    if (typeof line?.set_quantity === "function") {
        line.set_quantity(0);
    }
}

// Remove all reward lines for a given program
function _removeProgramRewardLines(order, programId) {
    const lines = [...(order.get_orderlines() || [])];
    for (const line of lines) {
        if (!line.is_reward_line) continue;
        const reward = order.pos.reward_by_id?.[line.reward_id];
        if (reward.reward_type === 'discount' && reward?.program_id?.id === programId) {
            _safeRemoveLine(order, line);
        }
    }
}

// Choose best inside a program:
//  - Prefer capped discounts by largest cap
//  - Else highest discount %/amount
//  - Optionally product rewards

function _pickBestInsideProgram(items) {
    if (!items.length) return null;
    const discounts = items.filter((x) => x.reward?.reward_type === "discount");

    if (discounts.length) {
        const capped = discounts.filter((x) => (x.reward?.discount_max_amount ?? 0) > 0);
        if (capped.length) {
            return capped.slice().sort(
                (a, b) => (b.reward.discount_max_amount ?? 0) - (a.reward.discount_max_amount ?? 0)
            )[0];
        }
        return discounts.slice().sort((a, b) => {
            const diffDisc = (b.reward?.discount ?? 0) - (a.reward?.discount ?? 0);
            if (diffDisc !== 0) return diffDisc;
            const diffCheapest = (b.reward?.cheapest_qty ?? 1) - (a.reward?.cheapest_qty ?? 1);
            if (diffCheapest !== 0) return diffCheapest;
            return (b.reward?.required_points ?? 0) - (a.reward?.required_points ?? 0);
        })[0];
    }
    return null;
}

// ------- main patch: Order -------
patch(Order.prototype, {
    _scheduleAutoRewards() {
        if (this._autoRewardsBusy) return;
        clearTimeout(this._autoRewardsTimer);
        this._autoRewardsTimer = setTimeout(() => this._recomputeAutoRewards(), 0);
    },

    async _recomputeAutoRewards() {
        if (this._autoRewardsBusy) return;
        this._autoRewardsBusy = true;
        try {
            await this._updatePrograms();
            const base = _orderBaseAmount(this);

            // Consider programs currently applied OR currently claimable
            const appliedIds = _appliedProgramIds(this);
            const firstClaimables = _getClaimables(this);
            const claimableIds = firstClaimables ? new Set(firstClaimables.map((x) => x.reward?.program_id?.id).filter(Boolean)) : [];
            const programsToCheck = new Set([...appliedIds, ...claimableIds]);

            for (const pid of programsToCheck) {
                // Find currently applied reward lines/fields for program pid
                const appliedRewardLines = [];
                const currentAppliedRewardId = (() => {
                    for (const line of this.get_orderlines()) {
                        const rid = line.reward_id || line.discount_reward;
                        if (rid) {
                            const r = this.pos.reward_by_id[rid];
                            if (r?.program_id?.id === pid) {
                                appliedRewardLines.push(line);
                            }
                        }
                    }
                    return appliedRewardLines[0]?.reward_id || appliedRewardLines[0]?.discount_reward || null;
                })();

                // Temporarily clear reward_id and points_cost on these lines so we can query claimables accurately
                const savedStates = appliedRewardLines.map(line => {
                    const state = {
                        line,
                        reward_id: line.reward_id,
                        discount_reward: line.discount_reward,
                        points_cost: line.points_cost,
                    };
                    line.reward_id = false;
                    if ('discount_reward' in line) line.discount_reward = false;
                    line.points_cost = 0;
                    return state;
                });

                // Re-query claimables for THIS program only
                const nowClaimables = _getClaimables(this).filter((x) => x.reward?.program_id?.id === pid);
                if (!nowClaimables.length) {
                    // Nothing valid anymore -> restore states first, then permanently clear them
                    for (const state of savedStates) {
                        state.line.reward_id = state.reward_id;
                        if ('discount_reward' in state.line) state.line.discount_reward = state.discount_reward;
                        state.line.points_cost = state.points_cost;
                    }
                    if (!this.locked) {
                        _removeProgramRewardLines(this, pid);
                        for (const line of this.get_orderlines()) {
                            const rid = line.reward_id || line.discount_reward;
                            if (rid) {
                                const r = this.pos.reward_by_id[rid];
                                if (r?.program_id?.id === pid) {
                                    line.reward_id = false;
                                    line.set_discount(0);
                                    if ('discount_reward' in line) line.set_discount_reward(false);
                                    line.coupon_id = null;
                                    line.points_cost = 0;
                                    line.reward_identifier_code = null;
                                }
                            }
                        }
                    }
                    continue;
                }

                const best = _pickBestInsideProgram(nowClaimables);

                // Buy 1 @ 20% and B2G1 are both in the same promotion. But both layers apply to the cart. HENIIS BUY1 G25% B2G1 CLF
                // DB: cmr-ctl-fashion-15-6-26
                const directRewardFullyApplied = (() => {
                    if (!best || !['specific', 'cheapest'].includes(best.reward.discount_applicability) || best.reward.buy_with_reward_price !== 'no' || best.reward.discount_max_amount) {
                        return true;
                    }
                    let eligibleLines = [];
                    if (best.reward.discount_applicability === 'specific') {
                        const applicableProducts = best.reward.all_discount_product_ids;
                        eligibleLines = this.get_orderlines().filter(line => line.quantity > 0 && !line.refunded_orderline_id &&
                            ((applicableProducts.has(line.get_product().id) && this._isRewardProductPartOfRuleSerial(best.reward, applicableProducts, line)) ||
                             (line.reward_product_id && applicableProducts.has(line.reward_product_id) && this._isRewardProductPartOfRuleSerial(best.reward, applicableProducts, line)))
                        );
                    } else if (best.reward.discount_applicability === 'cheapest') {
                        const program = best.reward.program_id;
                        const serialIds = new Set();
                        if (program && program.rules) {
                            program.rules.forEach(rule => {
                                if (rule.serial_ids) {
                                    rule.serial_ids.forEach(id => serialIds.add(id));
                                }
                            });
                        }
                        let candidates = this.get_orderlines().filter(line => line.quantity > 0 && !line.refunded_orderline_id);
                        if (serialIds.size) {
                            candidates = candidates.filter(line => {
                                const packLotLines = line.pack_lot_lines;
                                if (!packLotLines || !packLotLines.length) return false;
                                let lotId = false;
                                packLotLines.forEach(pack => {
                                    const stockLot = this.pos.stock_lots_by_name[pack.lot_name];
                                    if (stockLot) lotId = stockLot.stockLot.id;
                                });
                                return serialIds.has(lotId);
                            });
                        }
                        candidates.sort((a, b) => a.getComboTotalPriceWithoutTax() - b.getComboTotalPriceWithoutTax());
                        
                        const totalCandidatesQty = candidates.reduce((sum, line) => sum + line.get_quantity(), 0);
                        const activeRule = program.rules.find(rule => totalCandidatesQty >= rule.minimum_qty);
                        if (activeRule) {
                            const cheapestQtyNeeded = best.reward.cheapest_qty || 1;
                            let accumulatedQty = 0;
                            for (const line of candidates) {
                                if (accumulatedQty >= cheapestQtyNeeded) break;
                                eligibleLines.push(line);
                                accumulatedQty += line.get_quantity();
                            }
                        }
                    }
                    const sameLength = eligibleLines.length === appliedRewardLines.length;
                    const allEligibleAreApplied = eligibleLines.every(line => appliedRewardLines.includes(line));
                    const allHaveCorrectDiscount = eligibleLines.every(line => line.discount === best.reward.discount);
                    return sameLength && allEligibleAreApplied && allHaveCorrectDiscount;
                })();

                // If best reward is already applied, restore states and keep it!
                if (best && best.reward.id === currentAppliedRewardId && directRewardFullyApplied) {
                    for (const state of savedStates) {
                        state.line.reward_id = state.reward_id;
                        if ('discount_reward' in state.line) state.line.discount_reward = state.discount_reward;
                        state.line.points_cost = state.points_cost;
                    }
                    continue;
                }

                // Restore states so we can remove them cleanly
                for (const state of savedStates) {
                    state.line.reward_id = state.reward_id;
                    if ('discount_reward' in state.line) state.line.discount_reward = state.discount_reward;
                    state.line.points_cost = state.points_cost;
                }

                if (!best) {
                    const newClaimables = nowClaimables.filter((x) => x.reward?.reward_type === "discount_on_product");
                    if (newClaimables.length) {
                        const selectedLine = this.selected_orderline;
                        if (selectedLine && selectedLine.product) {
                            const selectedProdId = selectedLine.product.id;

                            // 1. Identify the reward record for the product the user just scanned/selected
                            const matchingClaim = newClaimables.sort((a, b) => {
                                const pointsA = a.reward.required_points || 0;
                                const pointsB = b.reward.required_points || 0;
                                return pointsB - pointsA;
                            }).find(claim =>
                                claim.reward?.cmr_discount_product_ids?.includes(selectedProdId)
                            );

                            if (matchingClaim) {
                                const program = matchingClaim.reward.program_id;
                                const reward = matchingClaim.reward;

                                // 2. Get the points + rules from your modified method
                                const result = this.pointsForPrograms([program], true)[program.id];

                                if (result && result.length) {
                                    const validPointData = result.find(item => {
                                        const rule = item.rule;
                                        if (!rule) return false;
                                        const rewardRuleId = Array.isArray(reward.ref_loyalty_rule_id) ? reward.ref_loyalty_rule_id[0] : reward.ref_loyalty_rule_id;
                                        const isCorrectRule = rewardRuleId ? (rule.id === rewardRuleId) : (item.points === reward.required_points);
                                        if (!isCorrectRule) return false;

                                        const contributingLines = this.get_orderlines().filter(l =>
                                            !l.refunded_orderline_id && this._cmrLineMatchesRule(rule, l, program)
                                        );
                                        const totalQty = contributingLines.reduce((sum, l) => sum + l.get_quantity(), 0);
                                        const totalAmt = contributingLines.reduce((sum, l) => sum + l.get_price_with_tax(), 0);

                                        return totalQty >= rule.minimum_qty && totalAmt >= rule.minimum_amount;
                                    });

                                    if (validPointData) {
                                        const earnedPoints = validPointData.points;
                                        const maxUsesAllowed = Math.floor(earnedPoints / (reward.required_points || 1));
                                        const usedUses = this.get_orderlines().filter(l =>
                                            l.reward_id === reward.id && l !== selectedLine
                                        ).length;

                                        if (usedUses < maxUsesAllowed) {
                                            selectedLine.reward_id = reward.id;
                                            this._updateRewards();
                                            return true;
                                        }
                                    }
                                }

                                if (selectedLine.reward_id === reward.id) {
                                    selectedLine.reward_id = false;
                                }
                            }
                        }
                    }
                }

                if (!best) continue;

                // Decide if we should upgrade: different rule or greater allowed amount
                const intended = _estimateIntended(best.reward, base);
                const cap = best.reward.discount_max_amount ?? 0;
                const allowed = cap > 0 ? Math.min(intended, cap) : intended;

                const currentAppliedAmt = _currentProgramDiscount(this, pid);
                const shouldUpgrade = allowed > currentAppliedAmt + EPS;
                if (shouldUpgrade || true) {
                    if (!this.locked) {
                        _removeProgramRewardLines(this, pid);
                        for (const line of this.get_orderlines()) {
                            const rid = line.reward_id || line.discount_reward;
                            if (rid) {
                                const r = this.pos.reward_by_id[rid];
                                if (r?.program_id?.id === pid) {
                                    line.reward_id = false;
                                    line.set_discount(0);
                                    if ('discount_reward' in line) line.set_discount_reward(false);
                                    line.coupon_id = null;
                                    line.points_cost = 0;
                                    line.reward_identifier_code = null;
                                }
                            }
                        }
                    }
                    await this._applyReward(best.reward, best.coupon_id, best.potentialQty);
                }
            }
        } finally {
            this._autoRewardsBusy = false;
        }
    },

    _updateRewards() {
        const res = super._updateRewards(...arguments);
        this._scheduleAutoRewards?.();
        return res;
    },

    _updateRewardLines() {
        const res = super._updateRewardLines(...arguments);
        this._scheduleAutoRewards?.();
        return res;
    },

    async _updatePrograms() {
        const res = super._updatePrograms ? await super._updatePrograms(...arguments) : undefined;
        this._scheduleAutoRewards?.();
        return res;
    },

    // --- user-facing mutators (safe wrappers) ---
    add_product() {
        const res = _origAddProduct ? _origAddProduct.apply(this, arguments) : undefined;
        this._scheduleAutoRewards?.();
        return res;
    },

    remove_orderline(line) {
        _safeRemoveLine(this, line);
        this._scheduleAutoRewards?.();
//        Pranav Start
        this.check_remove_unapplicable_reward_id();
//      Stop
        return;
    },

    set_partner() {
        const res = _origSetPartner ? _origSetPartner.apply(this, arguments) : undefined;
        this._scheduleAutoRewards?.();
        return res;
    },

    set_pricelist() {
        const res = _origSetPricelist ? _origSetPricelist.apply(this, arguments) : undefined;
        this._scheduleAutoRewards?.();
        return res;
    },

//    Pranav Start
    check_remove_unapplicable_reward_id() {
        if (this._autoRewardsBusy || this._cmrReapplyBusy) {
            return;
        }
        const reward_orderlines = this.orderlines.filter((l) => l.reward_id || l.discount_reward);
        for (const line of reward_orderlines) {
            let reward_id = line.reward_id || line.discount_reward;
            if (!reward_id) {
                continue;
            }
            const reward = this.pos.reward_by_id?.[reward_id];
            if (!reward?.program_id) {
                continue;
            }
            if (!line.coupon_id) {
                continue;
            }
            const couponPoints = this._getRealCouponPoints(line.coupon_id) + (line.points_cost || 0);
            if (couponPoints < reward.required_points) {
                line.reward_id = false;
                line.set_discount(0);
                line.set_discount_reward(false);
                line.coupon_id = null;
                line.points_cost = 0;
                line.reward_identifier_code = null;
            }
        }
        this._scheduleAutoRewards?.();
    },
//    Stop

});

// ------- patch Orderline once (react to qty/price/discount changes) -------
patch(Orderline.prototype, {
    set_quantity() {
        const res = _origSetQuantity ? _origSetQuantity.apply(this, arguments) : undefined;
        this.order?._scheduleAutoRewards?.();
        return res;
    },
    set_unit_price() {
        const res = _origSetUnitPrice ? _origSetUnitPrice.apply(this, arguments) : undefined;
        this.order?._scheduleAutoRewards?.();
        return res;
    },
    set_discount() {
        const res = _origSetDiscount ? _origSetDiscount.apply(this, arguments) : undefined;
        this.order?._scheduleAutoRewards?.();
        return res;
    },
    setPackLotLines() {
        const res = _origSetPackLotLines ? _origSetPackLotLines.apply(this, arguments) : undefined;
        this.order?._scheduleAutoRewards?.();
        return res;
    },
});
