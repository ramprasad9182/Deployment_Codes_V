/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { RewardButton } from "@pos_loyalty/app/control_buttons/reward_button/reward_button";

patch(RewardButton.prototype, {
    _filterLatestRuleRewards(claimableList, order) {
        if (!claimableList || claimableList.length <= 1) {
            return claimableList || [];
        }
        const programMap = new Map();
        for (const item of claimableList) {
            const programId = item.reward?.program_id?.id;
            if (!programId) continue;
            if (!programMap.has(programId)) {
                programMap.set(programId, []);
            }
            programMap.get(programId).push(item);
        }
        const finalResult = [];
        for (const [programId, items] of programMap.entries()) {
            if (items.length <= 1) {
                finalResult.push(...items);
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
            finalResult.push(bestItem);
        }
        return finalResult;
    },

    _getPotentialRewards() {
        const order = this.pos.get_order();
        let rewards = [];
        if (order) {
            const claimableRewards = order.getClaimableRewards();
            if (claimableRewards) {
                rewards = claimableRewards.filter(
                    ({ reward }) => reward.program_id.program_type !== "ewallet"
                );
            }
        }
        rewards = this._filterLatestRuleRewards(rewards, order);
        const discountRewards = rewards.filter(
            ({ reward }) => reward.reward_type === "discount"
        );
        const freeProductRewards = rewards.filter(
            ({ reward }) => reward.reward_type === "product"
        );
        const discountProductRewards = rewards.filter(
            ({ reward }) => reward.reward_type === "discount_on_product"
        );
        let potentialFreeProductRewards = this.pos.getPotentialFreeProductRewards();
        potentialFreeProductRewards = this._filterLatestRuleRewards(potentialFreeProductRewards, order);

        if (discountProductRewards.length > 0) {
            return discountProductRewards.concat(
                this._mergeFreeProductRewards(
                    freeProductRewards,
                    potentialFreeProductRewards
                )
            );
        } else {
            return discountRewards.concat(
                this._mergeFreeProductRewards(
                    freeProductRewards,
                    potentialFreeProductRewards
                )
            );
        }
    },

    hasClaimableRewards() {
        const order = this.pos.get_order();
        const get_potential_rewards = this._getPotentialRewards();
        if (get_potential_rewards.length > 0) {
            if (
                get_potential_rewards.filter(
                    ({ reward }) =>
                        reward.reward_type === "product" ||
                        reward.reward_type === "discount_on_product"
                ).length > 0
            ) {
                order.is_rew = true;
            } else {
                order.is_rew = false;
            }
        } else {
            order.is_rew = false;
        }
        return get_potential_rewards.length > 0;
    },

    async click() {
        const order = this.pos.get_order();
        const rewards = this._getPotentialRewards().filter(
            ({ reward }) =>
                order.block_auto_promotions ||
                reward.discount_max_amount > 0 ||
                reward.reward_type === "product" ||
                reward.reward_type === "discount_on_product" ||
                reward.reward_type === "discount"
        );
        if (rewards.length >= 1) {
            const rewardOptions = rewards.map((claimable) => {
                const reward = claimable.reward;
                const program = reward.program_id;
                let label = reward.description || reward.display_name || (program ? program.name : "");

                let prodId = null;
                if (reward.reward_product_ids && reward.reward_product_ids.length > 0) {
                    prodId = reward.reward_product_ids[0];
                } else if (reward.cmr_discount_product_ids && reward.cmr_discount_product_ids.length > 0) {
                    prodId = reward.cmr_discount_product_ids[0];
                }
                if (prodId) {
                    const prod = this.pos.db.get_product_by_id(prodId);
                    if (prod) {
                        if (reward.reward_type === "product") {
                            label = _t("Free Product - %s", prod.display_name);
                        } else if (reward.reward_type === "discount_on_product") {
                            label = _t("Discount Product - %s", prod.display_name);
                        }
                    }
                }
                return {
                    id: reward.id,
                    label: label,
                    description: program ? (program.name || "") : "",
                    item: claimable,
                };
            });

            const { confirmed, payload: selectedReward } = await this.popup.add(
                SelectionPopup,
                {
                    title: _t("Please select a reward"),
                    list: rewardOptions,
                }
            );
            if (confirmed && selectedReward) {
                const claimable = selectedReward.item || selectedReward;
                return this._applyReward(
                    claimable.reward,
                    claimable.coupon_id,
                    claimable.potentialQty
                );
            }
        }
        return false;
    },

    auto_apply_rewards() {
        let order = this.pos.get_order();
        if (order && order.block_auto_promotions) {
            return;
        }
    },

    async _applyReward(reward, coupon_id, potentialQty) {
        const order = this.pos.get_order();

        if (reward && reward.program_id) {
            if (typeof order.removeProgramRewards === "function") {
                order.removeProgramRewards(reward.program_id.id);
            } else {
                const lines = [...(order.get_orderlines() || [])];
                for (const line of lines) {
                    const rid = line.reward_id || line.discount_reward;
                    const r = rid ? this.pos.reward_by_id?.[rid] : null;
                    if (r?.program_id?.id === reward.program_id.id) {
                        if (line.is_reward_line || line.reward_product_id) {
                            order._unlinkOrderline(line);
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
            }
        }

        order.disabledRewards.delete(reward.id);

        const args = {};

        const getLotProductIds = (r) => {
            if (!r.stock_lot_ids || r.stock_lot_ids.size === 0) {
                return [];
            }
            const prodIds = new Set();
            for (const name in this.pos.stock_lots_by_name) {
                const lotObj = this.pos.stock_lots_by_name[name]?.stockLot;
                if (lotObj && r.stock_lot_ids.has(lotObj.id) && lotObj.product_id) {
                    prodIds.add(lotObj.product_id[0]);
                }
            }
            return Array.from(prodIds);
        };

        const lotProdIds = getLotProductIds(reward);
        let rewardProductIds = (reward.reward_product_ids || []);
        if (lotProdIds.length > 0) {
            rewardProductIds = lotProdIds;
        }

        if (reward.reward_type === "product" && (reward.multi_product || rewardProductIds.length > 1)) {
            const productsList = rewardProductIds.map(
                (product_id) => this.pos.db.get_product_by_id(product_id)
            ).filter(p => p).map((product) => ({
                id: product.id,
                label: product.display_name,
                item: product.id,
            }));

            if (productsList.length > 0) {
                const { confirmed, payload: selectedProduct } =
                    await this.popup.add(SelectionPopup, {
                        title: _t("Please select a product for this reward"),
                        list: productsList,
                    });

                if (!confirmed) {
                    return false;
                }

                args["product"] = selectedProduct;
            }
        }

        let discountProductIds = (reward.cmr_discount_product_ids || []);
        if (lotProdIds.length > 0) {
            discountProductIds = lotProdIds;
        }

        if (
            reward.reward_type === "discount_on_product" &&
            discountProductIds.length >= 1
        ) {
            const productsList = discountProductIds
                .map(id => this.pos.db.get_product_by_id(id))
                .filter(product => product)
                .map(product => ({
                    id: product.id,
                    label: product.display_name,
                    item: product.id,
                }));

            if (productsList.length > 0) {
                const { confirmed, payload: selectedProduct } =
                    await this.popup.add(SelectionPopup, {
                        title: _t("Please select a product for this reward"),
                        list: productsList,
                    });

                if (!confirmed) {
                    return false;
                }

                args["product"] = selectedProduct;
            }
        }

        if (
            (reward.reward_type == "product" &&
                reward.program_id.applies_on !== "both") ||
            (reward.program_id.applies_on == "both" && potentialQty)
        ) {
            const prodToUse = args["product"] || rewardProductIds[0] || (reward.reward_product_ids && reward.reward_product_ids[0]);
            this.pos.addProductToCurrentOrder(
                prodToUse,
                { quantity: potentialQty || 1 }
            );

            return true;
        } else if (
            reward.reward_type == "discount_on_product" ||
            (reward.program_id.applies_on == "both" && potentialQty)
        ) {
            const prodToUse = args["product"] || discountProductIds[0] || (reward.cmr_discount_product_ids && reward.cmr_discount_product_ids[0]);
            this.pos.addProductToCurrentOrder(
                prodToUse,
                {
                    quantity: potentialQty || 1,
                    reward_id: reward.id,
                }
            );

            console.log("total_lines", order.get_orderlines());

            return true;
        } else {
            const result = order._applyReward(reward, coupon_id, args);

            if (result !== true) {
                this.notification.add(result);
            }

            order._updateRewards();

            return result;
        }
    },
});
