/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Payment } from "@point_of_sale/app/store/models";

//if the employee gives discount beyond his limit then the manager needs to approve
patch(PaymentScreen.prototype, {
    /**
     * Override the validate button to approve discount limit
     */


    shouldDownloadInvoice() {
        return false;
    },

     async validateOrder(isForceValidate) {
        const order = this.currentOrder;

        // Calculate TOTAL CASH used
        const cashAmount = order.paymentlines
            .filter(line => line.payment_method?.is_cash_count)
            .reduce((sum, line) => sum + line.amount, 0);

        console.log('===>cashAmount ',cashAmount)

        if (cashAmount >= 200000) {
            await this.env.services.popup.add(ErrorPopup, {
                title: "Cash Limit Exceeded",
                body: "Cash payment is not allowed for amounts ₹200,000 above.",
            });
            return false;
        }

        // continue normal validation
        return super.validateOrder(isForceValidate);
    },

//    async _finalizeValidation() {
//        var order = this.pos.get_order();
//        var orderlines = this.currentOrder.get_orderlines();
//        var employee_dis = this.pos.get_cashier()["limited_discount"];
//        var employee_name = this.pos.get_cashier()["name"];
//        var flag = 1;
//
//        // Check line-wise discounts
//        //        orderlines.forEach((orderline) => {
//        //            if (orderline.discount > employee_dis) {
//        //                flag = 0;
//        //            }
//        //        });
//
//        const product = this.pos.db.get_product_by_id(
//            this.pos.config.discount_product_id[0]
//        );
//        const global_discount_product = orderlines.filter(
//            (line) => line.get_product() === product && !line.is_fix_discount_line
//        );
//        var global_discount_price = 0;
//        var order_payment_amount = 0;
//        if (global_discount_product.length > 0) {
//            global_discount_price = Math.round(
//                global_discount_product[0].price
//            );
//        }
//        if (order.paymentlines.length > 0) {
//            order_payment_amount = order.paymentlines[0].amount;
//        }
//        var total_order_price = Math.round(
//            global_discount_price - order_payment_amount
//        );
//        var global_discount_percentage = Math.round(
//            (global_discount_price / total_order_price) * 100
//        );
//        //        var global_discount = order.get_total_discount();
//        if (
//            global_discount_product.length > 0 &&
//            global_discount_percentage > employee_dis
//        ) {
//            flag = 0;
//        }
//
//        if (flag != 1) {
//            var managers = this.pos.employees.filter(
//                (obj) => obj.role == "manager"
//            );
//            if (managers.length == 0) {
//                this.popup.add(ErrorPopup, {
//                    title: _t("No Manager Available"),
//                    body: _t(
//                        employee_name +
//                            ", there are no managers available for approval."
//                    ),
//                });
//                return false;
//            }
//
//            var manager = managers[0]; // Assuming there's at least one manager
//            var manager_name = manager.name;
//
//            const { confirmed, payload } = await this.popup.add(NumberPopup, {
//                title: _t(
//                    employee_name +
//                        ", your discount is over the limit. \n Manager " +
//                        manager_name +
//                        " pin for Approval"
//                ),
//                isPassword: true,
//            });
//
//            if (confirmed) {
//                var pin = manager.pin;
//                if (Sha1.hash(payload) == pin) {
//                    //                    this.pos.showScreen(this.nextScreen);
//                    try {
//                        Sha1.hash(payload) == pin;
//                    } catch (error) {
//                        if (error instanceof ConnectionLostError) {
//                            this.pos.showScreen(this.nextScreen);
//                            Promise.reject(error);
//                            return error;
//                        } else {
//                            throw error;
//                        }
//                    }
//                } else {
//                    this.popup.add(ErrorPopup, {
//                        title: _t(" Manager Restricted your discount"),
//                        body: _t(
//                            employee_name +
//                                ", Manager " +
//                                manager_name +
//                                "'s pin is incorrect."
//                        ),
//                    });
//                    return false;
//                }
//            } else {
//                return false;
//            }
//        }
//
//        try {
//            this.currentOrder.finalized = true;
//        } catch (error) {
//            if (error instanceof ConnectionLostError) {
//                this.pos.showScreen(this.nextScreen);
//                Promise.reject(error);
//                return error;
//            } else {
//                throw error;
//            }
//        }
//        await super._finalizeValidation(...arguments);
//    },
});

patch(Payment.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments); // Call the original setup method
        this.credit_note_id = 0;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.credit_note_id = this.credit_note_id || 0;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.credit_note_id = json.credit_note_id || 0;
    },

    set_credit_note(value) {
        this.credit_note_id = value;
    },
});