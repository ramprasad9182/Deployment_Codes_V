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
    _getPotentialRewards() {
        const order = this.pos.get_order();
        const rewardLines = order
            .get_orderlines()
            .filter((line) => line.is_reward_line) // Filter for reward lines
            .map((line) => {
                const reward = this.pos.reward_by_id[line.reward_id]; // Get the reward by its ID
                return reward ? reward.program_id.id : null; // Return the program_id or null if not found
            })
            .filter((programId) => programId !== null);
        const discount_rewardLines = order
            .get_orderlines()
            .filter((line) => line.reward_id)
            .map((line) => {
                const reward = this.pos.reward_by_id[line.reward_id];
                return reward ? reward.program_id.id : null;
            })
            .filter((programId) => programId !== null);
        // Claimable rewards excluding those from eWallet programs.
        // eWallet rewards are handled in the eWalletButton.
        let rewards = [];
        if (order) {
            const claimableRewards = order.getClaimableRewards();
            if (claimableRewards) {
                rewards = claimableRewards.filter(
                    ({ reward }) =>
                        reward.program_id.program_type !== "ewallet" &&
                        !rewardLines.includes(reward.program_id.id)
                );
                if (discount_rewardLines) {
                    rewards = claimableRewards.filter(
                        ({ reward }) =>
                            reward.program_id.program_type !== "ewallet" &&
                            !discount_rewardLines.includes(reward.program_id.id)
                    );
                }
            }
        }
        //        const discountRewards = [];
        const discountRewards = rewards.filter(
            ({ reward }) => reward.reward_type == "discount"
        );
        const freeProductRewards = rewards.filter(
            ({ reward }) => reward.reward_type == "product"
        );
        const discountProductRewards = rewards.filter(
            ({ reward }) => reward.reward_type === "discount_on_product"
        );
        const potentialFreeProductRewards = this.pos.getPotentialFreeProductRewards();
        if (discountProductRewards.length > 0) {
            return discountProductRewards.concat(
                this._mergeFreeProductRewards(
                    freeProductRewards,
                    potentialFreeProductRewards)
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
            this.auto_apply_rewards();
        } else {
            order.is_rew = false;
        }
        //        return this._getPotentialRewards().filter(({ reward }) => reward.reward_type=== "product").length>0;
        return get_potential_rewards.length > 0;
    },

    async click() {
        const order = this.pos.get_order();
        //        const rewards = this._getPotentialRewards();
        const rewards = this._getPotentialRewards().filter(
            ({ reward }) =>
                reward.discount_max_amount > 0 ||
                reward.reward_type == "product" ||
                reward.reward_type === "discount_on_product"
        );
        if (rewards.length >= 1) {
            const rewardsList = rewards.reduce((acc, reward) => {
                const programId = reward.reward.program_id.id;
                if (!acc[programId]) {
                    acc[programId] = [];
                }
                acc[programId].push(reward);
                return acc;
            }, {});

            console.log("dd", rewardsList);
            const highestDiscountRewards = Object.values(rewardsList).map(
                (programRewards) => {
                    const maxDiscountReward = programRewards.reduce(
                        (max, current) => {
                            if (current.reward.discount_max_amount > 0) {
                                return current.reward.discount_max_amount >
                                    max.reward.discount_max_amount
                                    ? current
                                    : max;
                            }
                            console.log(
                                "current",
                                current.reward.product_price
                            );
                            console.log("max", max.reward.product_price);
                            if (
                                current.reward.reward_type ==
                                "discount_on_product"
                            ) {
                                let index = 0;
                                let price = 0;
                                let amount_total = 0;
                                for (const line of order.orderlines) {
                                    amount_total += line.price;
                                }
                                for (const rule of current.reward.program_id
                                    .rules) {
                                    if (amount_total >= rule.minimum_amount) {
                                        price = [
                                            ...current.reward.program_id
                                                .rewards,
                                        ].sort((a, b) => a.id - b.id)[index]
                                            .product_price;
                                        index += 1;
                                    }
                                }
                                return price === current.reward.product_price
                                    ? current
                                    : max; // Assuming `discount` exists
                            }
                            return current.reward.discount > max.reward.discount
                                ? current
                                : max; // Assuming `discount` exists
                        }
                    );
                    return {
                        id: maxDiscountReward.reward.id,
                        label: maxDiscountReward.reward.description,
                        description: maxDiscountReward.reward.program_id.name,
                        item: maxDiscountReward,
                    };
                }
            );
            console.log("highestDiscountRewards", highestDiscountRewards);
            //            highestDiscountRewards_lst = highestDiscountRewards.filter(({ reward }) => reward.reward_type=== "product")
            const { confirmed, payload: selectedReward } = await this.popup.add(
                SelectionPopup,
                {
                    title: _t("Please select a reward"),
                    list: highestDiscountRewards,
                }
            );
            if (confirmed) {
                return this._applyReward(
                    selectedReward.reward,
                    selectedReward.coupon_id,
                    selectedReward.potentialQty
                );
            }
        }
        return false;
    },
    auto_apply_rewards() {
        let order = this.pos.get_order();
        const rewards = this._getPotentialRewards();
        const rewardsList = rewards.reduce((acc, reward) => {
            const programId = reward.reward.program_id.id;
            if (!acc[programId]) {
                acc[programId] = [];
            }
            acc[programId].push(reward);
            return acc;
        }, {});
        const highestDiscountRewards = Object.values(rewardsList)
            .map((programRewards) => {
                // 1. Ensure we only look at rewards that actually exist
                const validRewards = programRewards.filter(r => r.reward);

                if (validRewards.length === 0) return null;

                // 2. Find the max discount without strictly excluding max_amount rewards
                const maxDiscountReward = validRewards.reduce((max, current) => {
                    const currentDisc = current.reward.discount || 0;
                    const maxDisc = max.reward.discount || 0;
                    return currentDisc > maxDisc ? current : max;
                }, validRewards[0]); // Initialize with the first reward to avoid errors

                // 3. Return the formatted object
                return {
                    id: maxDiscountReward.reward.id,
                    label: maxDiscountReward.reward.display_name || maxDiscountReward.reward.description,
                    description: maxDiscountReward.reward.program_id?.[1] || maxDiscountReward.reward.program_id.name,
                    item: maxDiscountReward,
                };
            })
            .filter((item) => item !== null);

        console.log("highest", highestDiscountRewards);
        for (var i = 0, l = highestDiscountRewards.length; i < l; ++i) {
            let reward = highestDiscountRewards[i]["item"]["reward"];
            let coupon_id = highestDiscountRewards[i]["item"]["coupon_id"];
            let potentialQty = highestDiscountRewards[i]["item"]["potentialQty"];
            order._applyReward(reward, coupon_id, potentialQty);
        }
    },

    async _applyReward(reward, coupon_id, potentialQty) {
        const order = this.pos.get_order();

        order.disabledRewards.delete(reward.id);

        const args = {};

        if (reward.reward_type === "product" && reward.multi_product) {
            const productsList = reward.reward_product_ids.map(
                (product_id) => ({
                    id: product_id,

                    label: this.pos.db.get_product_by_id(product_id)
                        .display_name,

                    item: product_id,
                })
            );

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

        if (
            reward.reward_type === "discount_on_product" &&
            // reward.discount_product_id.length >= 1
            reward.cmr_discount_product_ids.length >= 1
        ) {
            // // OLD
            // const productId = reward.discount_product_id[0];
            //
            // const product = this.pos.db.get_product_by_id(productId);
            //
            // const productsList = [];
            //
            // if (product) {
            //     productsList.push({
            //         id: product.id,
            //
            //         label: product.display_name,
            //
            //         item: product.id,
            //     });
            // } else {
            //     console.warn("Product not found in POS DB:", productId);
            // }
            // New
            const productsList = (reward.cmr_discount_product_ids || [])
                .map(id => this.pos.db.get_product_by_id(id))
                .filter(product => product)
                .map(product => ({
                    id: product.id,
                    label: product.display_name,
                    item: product.id,
                }));

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

        if (
            (reward.reward_type == "product" &&
                reward.program_id.applies_on !== "both") ||
            (reward.program_id.applies_on == "both" && potentialQty)
        ) {
            this.pos.addProductToCurrentOrder(
                args["product"] || reward.reward_product_ids[0],

                { quantity: potentialQty || 1 }
            );

            return true;
        } else if (
            reward.reward_type == "discount_on_product" ||
            (reward.program_id.applies_on == "both" && potentialQty)
        ) {
            this.pos.addProductToCurrentOrder(
                // args["product"] || reward.discount_product_id[0],
                args["product"] || reward.cmr_discount_product_ids[0],

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
                // Returned an error

                this.notification.add(result);
            }

            order._updateRewards();

            return result;
        }
    },
});
