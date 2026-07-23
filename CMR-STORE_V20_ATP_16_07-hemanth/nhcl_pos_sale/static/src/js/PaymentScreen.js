/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { onMounted, onWillUnmount, useState } from "@odoo/owl";


patch(PaymentScreen.prototype, {

    setup() {
        super.setup();
        this.kbState = useState({ highlightedId: null });

        // Fix 1: Bind and store the function reference explicitly
        this._boundOnPaymentKeyDown = this._onPaymentKeyDown.bind(this);

        onMounted(() => {
//            this.removeGiftVoucherPaymentIfNoProduct();

            // Set initial highlight to the first method safely
            const methods = this.payment_methods_from_config;
            if (methods && methods.length > 0) {
                this.kbState.highlightedId = methods[0].id;
            }

            // Use the stored reference
            window.addEventListener("keydown", this._boundOnPaymentKeyDown);
        });

        onWillUnmount(() => {
            // Use the exact same stored reference to successfully remove it
            window.removeEventListener("keydown", this._boundOnPaymentKeyDown);
        });
    },

    _onPaymentKeyDown(ev) {
        // Fix 2: Extra safety check to verify this specific component is active
        if (!this.props.isShown) return;

        const methods = this.payment_methods_from_config;
        if (!methods || methods.length === 0) return;

        const currentIndex = methods.findIndex(m => m.id === this.kbState.highlightedId);

        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            const nextIndex = (currentIndex + 1) % methods.length;
            this.kbState.highlightedId = methods[nextIndex].id;
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            const prevIndex = (currentIndex - 1 + methods.length) % methods.length;
            this.kbState.highlightedId = methods[prevIndex].id;
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const selectedMethod = methods.find(m => m.id === this.kbState.highlightedId);
            if (selectedMethod) {
                this.upiNewPaymentLine(selectedMethod);
            }
        } else if (ev.key === "Delete") {
            ev.preventDefault();
            if (this.selectedPaymentLine) {
                this.deletePaymentLine(this.selectedPaymentLine.cid);
            }
        }
    },

    async upiNewPaymentLine(paymentMethod) {
        const order = this.currentOrder;
        if (!order) return false;

        const same_paymentlines = order.paymentlines.filter(
            (paymentline) =>
                paymentline.payment_method.id === paymentMethod.id
        )
        if (same_paymentlines.length > 0) {
            this.selectPaymentLine(same_paymentlines[0].cid);
            // this.popup.add(ErrorPopup, {
            //     title: _t("Payment Method Already Added"),
            //     body: _t("This payment method has already been added!"),
            // });
            return false;
        }

        if (order.get_due() <= 0 && order.get_total_with_tax() > 0) {
            this.popup.add(ErrorPopup, {
                title: _t("No Due Amount"),
                body: _t("There is no due amount remaining for this order!"),
            });
            return false;
        }

//        const restrictedPayments = [
//            "Gift Voucher",
////            "Credit Note Settlement",
//            "Advance Payment",
//        ];
//
//        if (restrictedPayments.includes(paymentMethod.name)) {
//            this.popup.add(ErrorPopup, {
//                title: _t("Invalid Payment Method"),
//                body: _t("The selected payment method cannot be added manually."),
//            });
//            return false;
//        }

        return super.upiNewPaymentLine(...arguments);
    },

//    removeGiftVoucherPaymentIfNoProduct() {
//        const order = this.currentOrder;
//
//        const hasGiftVoucherProduct = order.get_orderlines().some(
//            (line) => line.product.display_name === "Gift Voucher"
//        );
//
//        // Find Gift Voucher payment line
//        const giftPaymentLine = order.paymentlines.find(
//            (line) => line.payment_method.name === "Gift Voucher"
//        );
//
//        // Remove payment line if product does not exist
//        if (!hasGiftVoucherProduct && giftPaymentLine) {
//            order.remove_paymentline(giftPaymentLine);
//        }
//    },

    addNewPaymentLine(paymentMethod) {
        const order = this.currentOrder;

        const same_paymentlines = order.paymentlines.filter(
            (paymentline) =>
                paymentline.payment_method.id === paymentMethod.id
        )
        if (same_paymentlines.length > 0) {
            this.selectPaymentLine(same_paymentlines[0].cid);
            // this.popup.add(ErrorPopup, {
            //     title: _t("Payment Method Already Added"),
            //     body: _t("This payment method has already been added!"),
            // });
            return false;
        }

        if (order.get_due() <= 0 && order.get_total_with_tax() > 0) {
            this.popup.add(ErrorPopup, {
                title: _t("No Due Amount"),
                body: _t("There is no due amount remaining for this order!"),
            });
            return false;
        }

        // Call original method if conditions pass
        return super.addNewPaymentLine(...arguments);
    },

//    deletePaymentLine(cid) {
//        const line = this.currentOrder.paymentlines.find(
//            (paymentline) => paymentline.cid === cid
//        );
//
//        if (line && line.payment_method.name === "Gift Voucher") {
//            this.popup.add(ErrorPopup, {
//                title: _t("Restricted Action"),
//                body: _t("Gift Voucher payment cannot be removed from Payment Screen."),
//            });
//            return;
//        }
//
//        return super.deletePaymentLine(...arguments);
//    },

    updateSelectedPaymentline(amount = false) {
        if (!this.selectedPaymentLine) {
            return;
        } // do nothing if no selected payment line

        const payment_method = this.selectedPaymentLine.payment_method;
        if (payment_method.is_credit_settlement) {
            this.popup.add(ErrorPopup, {
                title: _t("Payment Error"),
                body: _t("You can't change on Credit Note Settlement payment method!"),
            });
            return;
        }

//        if(payment_method.name === "Gift Voucher"){
//            this.popup.add(ErrorPopup, {
//                title: _t("Payment Error"),
//                body: _t("You can't change on Gift Voucher payment method!"),
//            });
//            return;
//        }
        const old_payment_line_amount = this.selectedPaymentLine.amount;

        const res = super.updateSelectedPaymentline(...arguments);

        if (payment_method.type === "bank") {
            if (amount === false) {
                if (this.numberBuffer.get() === null) {
                    amount = null;
                } else if (this.numberBuffer.get() === "") {
                    amount = 0;
                } else {
                    amount = this.numberBuffer.getFloat();
                }

            }
            const order = this.currentOrder;
            const change = order.get_change();
            if (amount && change) {
                this.selectedPaymentLine.set_amount(old_payment_line_amount);
                this.popup.add(ErrorPopup, {
                    title: _t("Bank Type Payment Error"),
                    body: _t("You can't set more than remaining payment on bank type payment method!"),
                });
                return;
            }
        }

        // Call original method if conditions pass
        return res;
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const zeroPayments = order.paymentlines.filter(
            (line) => line.amount === 0
        );
        if (zeroPayments.length > 0) {
            const paymentNames = zeroPayments
                .map((l) => l.payment_method.name)
                .join(", ");

            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Payment With Zero Amount "),
                body: _t(
                    `These payment methods have 0 amount:\n${paymentNames}\n\nPlease remove them before validating.`
                ),
                confirmText: _t("OK"),
                cancelText: _t("Cancel"),
            });

            return;
        }
        return super.validateOrder(...arguments);
    },

})