/** @odoo-module */
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    static: {
        props: {
            ...Orderline.props,
            line: {
                ...Orderline.props.line,
                shape: {
                    ...Orderline.props.line.shape,
                    empNo: { type: String, optional: true },
                    badge: { type: String, optional: true },
                    empId: { type: Number, optional: true },
                    proId: { type: Boolean, optional: true },
                    promo: { type: Number, optional: true },
                    promodisclines: { type: Array, optional: true },
                    barcode: { type: String, optional: true },
                    product_tax: { type: String, optional: true },
                    product_mrp: { type: String, optional: true },
                    gdiscount: { type: Number, optional: true },
                     discount_minimum_amount: { type: Number, optional: true },
                    discount_reward: { type: Number, optional: true },
                },
            },
        },
    },
});
