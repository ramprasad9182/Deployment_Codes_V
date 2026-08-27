/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/store/models";

patch(Orderline.prototype, {

    getDisplayClasses() {
        const isProductScreen =
            this.pos.mainScreen.component?.name === "ProductScreen";

        if (!isProductScreen) {
            return super.getDisplayClasses();
        }

        const hasDiscount = !!this.discount;
        const hasGDiscount = !!this.gdiscount;
        const isPromo = !!this.reward_id;

        const hasPromoOrDiscount = isPromo || hasDiscount;

        const superClasses = super.getDisplayClasses();

        // BOTH DISCOUNTS → Peach
        if (hasPromoOrDiscount && hasGDiscount) {
            return {
                ...superClasses,
                "multi-discount-highlight": true,
            };
        }

        // PROMO OR DISCOUNT → Yellow
        if (hasPromoOrDiscount) {
            return {
                ...superClasses,
                "promo-highlight": true,
            };
        }

        // GLOBAL DISCOUNT → Green
        if (hasGDiscount) {
            return {
                ...superClasses,
                "single-discount-highlight": true,
            };
        }

        return superClasses;
    }
});