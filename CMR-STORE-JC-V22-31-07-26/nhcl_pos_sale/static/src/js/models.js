/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Order , Payment,Orderline} from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

patch(Order.prototype, {
    // Pranav Start
    // async set_partner(partner) {
    //     super.set_partner(partner);
    //     const wallet_amount = this.get_partner()?.wallet_amount || 0.00;
    //     if (wallet_amount) {
    //         await this.env.services.popup.add(ConfirmPopup, {
    //             title: _t("Customer has Wallet Balance"),
    //             body: _t('The customer has a wallet balance of ₹ %s.', wallet_amount),
    //         });
    //     }
    // },
    async add_product(product, options) {
        const result = await super.add_product(...arguments);
        const totalAmount = typeof this.get_custom_totalwithtax === 'function' ? this.get_custom_totalwithtax() : this.get_total_with_tax();
        if (totalAmount > 190000) {
            const orderline = this.get_selected_orderline();
            if (orderline) {
                this.remove_orderline(orderline);
            }
            await this.pos.env.services.popup.add(ErrorPopup, {
                title: _t("Order Amount Limit Reached"),
                body: _t("Please reduce the order total to ₹1,90,000 or less and complete the payment. Move the remaining items to a new order."),
            });
        }
        return result;
    },

    //see set_screen_data
    get_screen_data() {
        const screen = this.screen_data["value"];
        // If no screen data is saved
        //   no payment line -> product screen
        //   with payment line -> payment screen
        if (!screen) {
            return { name: "ProductScreen" };
        }
        if (!this.finalized && this.get_paymentlines().length > 0) {
            return { name: "ProductScreen" };
        }
        return screen;
    },

    get credit_note_amount() {
        if (!this.credit_ids_list || this.credit_ids_list.length === 0) {
            const raw = this._credit_note_amount || 0.00;
            const total = typeof this.get_custom_totalwithtax === 'function' ? this.get_custom_totalwithtax() : (typeof this.get_total_with_tax === 'function' ? this.get_total_with_tax() : 0);
            return Math.round(Math.min(Math.max(0, total), raw));
        }
        const raw_credit = this.credit_ids_list.reduce((sum, credit) => sum + Math.round(credit.remaining_amount || 0), 0);
        let existing_amt = 0;
        if (this.paymentlines) {
            for (const line of this.paymentlines) {
                if (line.payment_method && !line.payment_method.is_credit_settlement) {
                    existing_amt += (line.amount || 0);
                }
            }
        }
        const total = typeof this.get_custom_totalwithtax === 'function' ? this.get_custom_totalwithtax() : (typeof this.get_total_with_tax === 'function' ? this.get_total_with_tax() : 0);
        const available_total = Math.max(0, total - existing_amt);
        return Math.round(Math.min(available_total, raw_credit));
    },

    set credit_note_amount(value) {
        this._credit_note_amount = value;
    },

    get credit_note_amounts() {
        if (!this.credit_ids_list || this.credit_ids_list.length === 0) {
            return this._credit_note_amounts || [];
        }
        const indexed = this.credit_ids_list.map((item, index) => ({ ...item, index }));
        let remain_total = typeof this.get_custom_totalwithtax === 'function' ? this.get_custom_totalwithtax() : (typeof this.get_total_with_tax === 'function' ? this.get_total_with_tax() : 0);
        if (this.paymentlines) {
            for (const line of this.paymentlines) {
                if (line.payment_method && !line.payment_method.is_credit_settlement) {
                    remain_total -= (line.amount || 0);
                }
            }
        }
        remain_total = Math.max(0, remain_total);
        const sorted = [...indexed].sort((a, b) => a.remaining_amount - b.remaining_amount);
        const used = new Array(this.credit_ids_list.length).fill(0);
        for (const item of sorted) {
            if (remain_total <= 0) break;
            const take = Math.round(Math.min(item.remaining_amount, remain_total));
            used[item.index] = take;
            remain_total -= take;
        }
        return used;
    },

    set credit_note_amounts(value) {
        this._credit_note_amounts = value;
    },

    get_custom_totalwithtax() {
        const orderlines = this.get_orderlines();
        const totalPriceWithTax = orderlines.reduce((sum, line) => {
            return sum + line.get_all_prices().priceWithTax;
        }, 0);
        return totalPriceWithTax;
    },

    get_custom_display_total() {
        const displayTotal = this.get_custom_totalwithtax() - this.credit_note_amount;
        return Math.max(0, displayTotal);
    },

    // Stop

    _mergeFreeProductRewards(freeProductRewards, potentialFreeProductRewards) {
        const result = [];
        for (const reward of potentialFreeProductRewards) {
            if (!freeProductRewards.find((item) => item.reward.id === reward.reward.id)) {
                result.push(reward);
            }
        }
        return freeProductRewards.concat(result);
    },

    _validGetPotentialRewards() {
        const order = this.pos.get_order();
         const rewardLines = order.get_orderlines()
        .filter(line => line.is_reward_line)
        .map(line => {
            const reward = this.pos.reward_by_id[line.reward_id];
            return reward ? reward.program_id.id : null;
        })
        .filter(programId => programId !== null);

        let rewards = [];
        if (order) {
            const claimableRewards = order.getClaimableRewards();
            if (claimableRewards) {
                rewards = claimableRewards.filter(
                    ({ reward }) => reward.program_id.program_type !== "ewallet"  &&
                        !rewardLines.includes(reward.program_id.id)
                );
            }
        }
        const discountRewards = rewards.filter(({ reward }) => reward.reward_type == "discount");
        const freeProductRewards = rewards.filter(({ reward }) => reward.reward_type == "product");
        const potentialFreeProductRewards = this.pos.getPotentialFreeProductRewards();
   return discountRewards.concat(
        this._mergeFreeProductRewards(freeProductRewards, potentialFreeProductRewards)
    );
    },

    set_partner(partner) {
        if (partner && this.credit_partner && partner.id !== this.credit_partner) {
            this.credit_note_amount = 0.00;
            this.credit_id = 0;
            this.credit_ids = [];
            this.credit_ids_list = [];
            this.credit_partner = false;
            this.credit_note_amounts = [];
        }
        return super.set_partner(...arguments);
    },

    remove_paymentline(line) {
        this.assert_editable();
        if (this.selected_paymentline === line) {
            this.select_paymentline(undefined);
        }
        this.paymentlines.remove(line);
        if (line.payment_method.is_credit_settlement) {
            if (line.order.get_partner() && line.order.get_partner().wallet_amount !== undefined) {
                line.order.get_partner().wallet_amount += line.amount;
            }
        }
    },

    // A value entry option is required for payment methods instead of automatically taking the total amount at once.
    add_paymentline(payment_method) {
        const paymentLine = super.add_paymentline(...arguments);
        // if (paymentLine && ['cash', 'mobikwik'].includes(paymentLine.name.toLowerCase())) {
        //     paymentLine.set_amount(0.00);
        // }
        if (paymentLine) {
            paymentLine.set_amount(0.00);
        }
        return paymentLine;
    },

    async pay() {
    const order = this.pos.get_order();

    // 1. Ensure customer is selected
    if (!order || !order.get_partner()) {
        await this.pos.selectPartner();
        if (!order || !order.get_partner()) {
            return false;
        }
        // await this.pos.env.services.popup.add(ErrorPopup, {
        //     title: _t("Customer Not Giving"),
        //     body: _t("Please add a customer and try again"),
        // });
        // return false;
    }

    // 2. Prevent zero-quantity products
    const filteredOrderLines = this.get_orderlines().filter((line) => line.quantity === 0);
    if (filteredOrderLines.length > 0) {
        await this.pos.env.services.popup.add(ErrorPopup, {
            title: _t("Zero Quantity Not Allowed"),
            body: _t("Product with Zero Quantity not allowed"),
        });
        return;
    }

    // 3. Setup credit application
    const partner = this.get_partner();
    let credit_amount = 0;
    let existing_amt = 0;
    for (const line of this.paymentlines) {
        if (!line.payment_method.is_credit_settlement) {
            existing_amt += line.amount;
        }
    }
    if (partner && partner.id === order.credit_partner) {
        const total = order.get_total_with_tax() + order.get_rounding_applied();
        const redeem_amount = order.credit_note_amount || 0;
        const amt = total - existing_amt;
        credit_amount = Math.min(amt, redeem_amount);
    }

    // 4. Apply credit payment line
    if (partner && credit_amount > 0) {
        const credit_methods = this.pos.payment_methods.filter(
            (method) =>
                method.is_credit_settlement === true &&
                this.pos.config.payment_method_ids.includes(method.id)
        );
        if (credit_methods.length > 0) {
            const credit_method = credit_methods[0];
            const existingLine = this.paymentlines.find(
                (line) => line.payment_method.id === credit_method.id
            );
            if (!existingLine) {
                const newPaymentline = new Payment(
                    { env: this.env },
                    {
                        order: this,
                        payment_method: credit_method,
                        pos: this.pos,
                    }
                );
                newPaymentline.set_amount(credit_amount);
                newPaymentline.set_credit_note(this.credit_id);
                this.paymentlines.add(newPaymentline);
            } else {
                existingLine.set_amount(credit_amount);
                existingLine.set_credit_note(this.credit_id);
            }
        } else {
            await this.pos.env.services.popup.add(ErrorPopup, {
                title: _t("Missing Payment Method"),
                body: _t("Credit settlement method is not configured."),
            });
            return;
        }
    }

    // 5. Check for reward conflicts
//    const rewards = this._validGetPotentialRewards().filter(
//        ({ reward }) =>
//             (reward.discount_max_amount > 0 && reward.buy_with_reward_price ==='no') || reward.reward_type === 'discount'
//    );
//    if (rewards.length > 0) {
//        await this.env.services.popup.add(ErrorPopup, {
//            title: _t("Apply Rewards"),
//            body: _t("Please apply one reward before proceeding."),
//        });
//        return;
//    }

    // 6. Proceed with default payment flow
    super.pay();
},

    remove_auto_promolines(rewardlines) {
        for (var rewardline of rewardlines) {
            const reward = this.pos.reward_by_id[rewardline.reward_id];
            if (reward.discount_applicability != 'order') {
                for (var promodiscline of rewardline.promodisclines) {
                    if (promodiscline) {
                        var remove_line = this.get_orderlines().find( (line) => line.cid === promodiscline);
                        if (remove_line) {
                            remove_line.promo = 0;
                        }
                    } else {
                        continue;
                    }
                }
            }
        }
    },

    _resetPrograms() {
        this.disabledRewards = new Set();
        this.codeActivatedProgramRules = [];
        this.codeActivatedCoupons = [];
        this.couponPointChanges = {};
        this.remove_auto_promolines(this._get_reward_lines())
        this.orderlines.remove(this._get_reward_lines());
        this._updateRewards();
    },

    _removePrograms() {
        this.block_auto_promotions = true;
        this.disabledRewards = new Set();
        this.codeActivatedProgramRules = [];
        this.codeActivatedCoupons = [];
        this.couponPointChanges = {};
        this.remove_auto_promolines(this._get_reward_lines());
        for (const line of this._get_reward_lines()) {
            this.orderlines.remove(line);
        }
        for (const line of this.orderlines) {
            if (line.reward_id) {
                line.reward_id = false;
                line.set_discount(0);
                line.set_discount_reward(false);
                line.coupon_id = null;
                line.points_cost = 0;
                line.reward_identifier_code = null;
            }
        }
        this._updateRewards();
    },

    _applyReward(reward, coupon_id, args) {

        // call parent logic first
        const result = super._applyReward(reward, coupon_id, args);



        if (result === true && reward.reward_type === "product") {

            const order = this.pos.get_order();



            // reward_product_id is Many2one -> [id, name]

            const rewardProductId = reward.reward_product_id?.[0];

            const rewardProductName = reward.reward_product_id?.[1];



            if (rewardProductId) {

                order.get_orderlines().forEach(line => {

                    if (line.product.id === rewardProductId) {

                        // tag this orderline for later serial validation

                        line.is_reward_line = true;

                        line.reward_id = reward.id;

                        line.reward_product_id = rewardProductId;

                        line.reward_product_name = rewardProductName;



                        console.log(

                            "Tagged reward orderline:",

                            rewardProductName,

                            "ID:", rewardProductId,

                            "Reward ID:", reward.id

                        );

                    }

                });

            } else {

                console.warn("reward_product_id not set on reward:", reward);

            }

        }

        // // OLD
        // else if (result === true && reward.reward_type === "discount_on_product") {
        //
        //     const order = this.pos.get_order();
        //
        //
        //
        //     // reward_product_id is Many2one -> [id, name]
        //
        //     const rewardProductId = reward.discount_product_id?.[0];
        //
        //     const rewardProductName = reward.discount_product_id?.[1];
        //
        //
        //
        //     if (rewardProductId) {
        //
        //         order.get_orderlines().forEach(line => {
        //
        //             if (line.product.id === rewardProductId) {
        //
        //                 // tag this orderline for later serial validation
        //
        //                 line.is_reward_line = true;
        //
        //                 line.reward_id = reward.id;
        //
        //                 line.reward_product_id = rewardProductId;
        //
        //                 line.reward_product_name = rewardProductName;
        //
        //
        //
        //                 console.log(
        //
        //                     "Tagged reward orderline:",
        //
        //                     rewardProductName,
        //
        //                     "ID:", rewardProductId,
        //
        //                     "Reward ID:", reward.id
        //
        //                 );
        //
        //             }
        //
        //         });
        //
        //     } else {
        //
        //         console.warn("reward_product_id not set on reward:", reward);
        //
        //     }
        //
        // }
        // New
        else if (result === true && reward.reward_type === "discount_on_product") {
            const order = this.pos.get_order();
            let rewardProductIds = [];
            // Handle both formats
            if (Array.isArray(reward.cmr_discount_product_ids)) {
                if (typeof reward.cmr_discount_product_ids[0] === "number") {
                    // Flat array: [1, 2, 3]
                    rewardProductIds = reward.cmr_discount_product_ids;
                } else if (Array.isArray(reward.cmr_discount_product_ids[0])) {
                    // Command format: [[6, 0, [1,2,3]]]
                    rewardProductIds = reward.cmr_discount_product_ids[0][2] || [];
                }
            }
            if (rewardProductIds.length) {
                order.get_orderlines().forEach(line => {
                    if (rewardProductIds.includes(line.product.id)) {
                        // tag this orderline for later serial validation
                        line.is_reward_line = true;
                        line.reward_id = reward.id;
                        line.reward_product_id = line.product.id;
                        line.reward_product_name = line.product.display_name;
                        console.log(
                            "Tagged reward orderline:",
                            line.product.display_name,
                            "ID:", line.product.id,
                            "Reward ID:", reward.id
                        );
                    }
                });
            } else {
                console.warn("cmr_discount_product_ids not set or empty:", reward);
            }
        }

        return result;
    },

});

