/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { onMounted, onWillUnmount, useState } from "@odoo/owl";
import { session } from "@web/session";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { Payment } from "@point_of_sale/app/store/models";

// Patch PaymentScreen
patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.kbState = useState({ highlightedId: null });

        // Fix 1: Bind and store the function reference explicitly
        this._boundOnPaymentKeyDown = this._onPaymentKeyDown.bind(this);

        onMounted(() => {
            if (!this.currentOrder?.get_partner()) {
                this.pos.showScreen('ProductScreen');
                this.popup.add(ErrorPopup, {
                    title: _t("Customer Required"),
                    body: _t("Please select a customer before proceeding to payment."),
                });
                return;
            }
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

    clickBack() {
        const order = this.currentOrder;
        if (order) {
            while (order.paymentlines.length > 0) {
                order.remove_paymentline(order.paymentlines[0]);
            }
        }
        this.pos.showScreen('ProductScreen');
    },

    _onPaymentKeyDown(ev) {
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
            (paymentline) => paymentline.payment_method.id === paymentMethod.id
        );
        if (same_paymentlines.length > 0) {
            this.selectPaymentLine(same_paymentlines[0].cid);
            return false;
        }

        if (order.get_due() <= 0 && order.get_total_with_tax() > 0) {
            this.popup.add(ErrorPopup, {
                title: _t("No Due Amount"),
                body: _t("There is no due amount remaining for this order!"),
            });
            return false;
        }

        const restrictedPayments = ["Credit Note Settlement"];
        if (restrictedPayments.includes(paymentMethod.name)) {
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Payment Method"),
                body: _t("The selected payment method cannot be added manually."),
            });
            return false;
        }

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
            (paymentline) => paymentline.payment_method.id === paymentMethod.id
        );
        if (same_paymentlines.length > 0) {
            this.selectPaymentLine(same_paymentlines[0].cid);
            return false;
        }

        if (order.get_due() <= 0 && order.get_total_with_tax() > 0) {
            this.popup.add(ErrorPopup, {
                title: _t("No Due Amount"),
                body: _t("There is no due amount remaining for this order!"),
            });
            return false;
        }

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
        if (!this.selectedPaymentLine) return;

        const payment_method = this.selectedPaymentLine.payment_method;
        if (payment_method.is_credit_settlement) {
            this.popup.add(ErrorPopup, {
                title: _t("Payment Error"),
                body: _t("You can't change on Credit Note Settlement payment method!"),
            });
            return;
        }

        let inputAmount = amount;
        if (inputAmount === false) {
            if (this.numberBuffer.get() === null) {
                inputAmount = null;
            } else if (this.numberBuffer.get() === "") {
                inputAmount = 0;
            } else {
                inputAmount = this.numberBuffer.getFloat();
            }
        }

        // ── DECIMAL BLOCK: reject paise entries ─────────────────────────
        // Only whole rupees allowed. If cashier enters 7500.01,
        // the decimal portion (0.01) is rejected with an error.
        if (inputAmount !== null && inputAmount !== 0) {
            const rounded = Math.round(inputAmount);
            if (Math.abs(inputAmount - rounded) > 0.001) {
                this.popup.add(ErrorPopup, {
                    title: _t("Invalid Amount"),
                    body: _t(
                        "Decimal (paise) amounts are not allowed. " +
                        "Please enter whole rupees only."
                    ),
                });
                this.numberBuffer.reset();
                return;
            }
        }

        const order = this.currentOrder;
        if (order && order.get_total_with_tax() >= 0 && inputAmount !== null && inputAmount < 0) {
            this.popup.add(ErrorPopup, {
                title: _t("Payment Error"),
                body: _t("Negative payment amount is not allowed!"),
            });
            this.numberBuffer.reset();
            return;
        }

        const old_payment_line_amount = this.selectedPaymentLine.amount;
        const res = super.updateSelectedPaymentline(...arguments);

        if (amount === false) {
            if (this.numberBuffer.get() === null) {
                amount = null;
            } else if (this.numberBuffer.get() === "") {
                amount = 0;
            } else {
                amount = this.numberBuffer.getFloat();
            }
        }
        const change = order.get_change();
        if (amount && change) {
            this.selectedPaymentLine.set_amount(old_payment_line_amount);
            this.popup.add(ErrorPopup, {
                title: _t("Payment Error"),
                body: _t("You can't set more than remaining payment on bank type payment method!"),
            });
            return;
        }

        return res;
    },

    shouldDownloadInvoice() {
        return false;
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;

        // 1. Change check
        if (order) {

            // Check each payment line for decimal amounts (paise)
            const decimalLines = order.paymentlines.filter(line => {
                const rounded = Math.round(line.amount);
                return Math.abs(line.amount - rounded) > 0.001;
            });
            if (decimalLines.length > 0) {
                const methods = decimalLines.map(l => l.payment_method.name).join(", ");
                await this.popup.add(ErrorPopup, {
                    title: _t("Invalid Amount"),
                    body: _t(
                        `Payment line(s) [${methods}] contain decimal (paise) amounts. ` +
                        `Only whole rupee amounts are allowed.`
                    ),
                });
                return;
            }
            const change = order.get_change();
            if (change > 0) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Validation Error"),
                    body: _t(
                        `Change amount of ${change.toFixed(2)} is not allowed. Please adjust the payment to exactly match the total due.`
                    ),
                });
                return false;
            }
        }

        // 2. Negative payments check
        if (order && order.get_total_with_tax() >= 0) {
            const negativePayments = order.paymentlines.filter(
                (line) => line.amount < 0
            );
            if (negativePayments.length > 0) {
                const paymentNames = negativePayments
                    .map((l) => l.payment_method.name)
                    .join(", ");
                await this.popup.add(ErrorPopup, {
                    title: _t("Payment Error"),
                    body: _t(
                        `These payment methods have negative amount:\n${paymentNames}\n\nPlease remove or correct them before validating.`
                    ),
                });
                return false;
            }
        }

        // 3. Zero payments check
        const zeroPayments = order?.paymentlines.filter(
            (line) => line.amount === 0
        ) || [];
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
            return false;
        }

        // 4. Check if there are any sold serial numbers in the order
        if (order) {
            const lotNameToLine = {};
            const lotNames = [];
            for (const line of order.get_orderlines()) {
                if (line.product.tracking === 'serial') {
                    const lotLines = line.pack_lot_lines;
                    if (lotLines && lotLines.length > 0) {
                        for (const lotLine of lotLines) {
                            const lotName = lotLine.lot_name;
                            if (lotName) {
                                lotNames.push(lotName);
                                if (!lotNameToLine[lotName]) {
                                    lotNameToLine[lotName] = [];
                                }
                                lotNameToLine[lotName].push(line);
                            }
                        }
                    }
                }
            }

            if (lotNames.length > 0) {
                const domain = [
                    ['name', 'in', lotNames],
                    ['product_qty_pos', '>', 0]
                ];
                try {
                    const availableLots = await this.pos.orm.call('stock.lot', 'search_read', [domain, ['name', 'product_qty_pos']]);
                    const availableLotNames = new Set(availableLots.map(lot => lot.name));

                    const soldSerialLines = [];
                    for (const lotName of lotNames) {
                        if (!availableLotNames.has(lotName)) {
                            const lines = lotNameToLine[lotName];
                            for (const line of lines) {
                                soldSerialLines.push({
                                    productName: line.product.display_name,
                                    serialNo: lotName
                                });
                            }
                        }
                    }

                    if (soldSerialLines.length > 0) {
                        const bodyText = soldSerialLines.map(item => `${item.productName} (Serial: ${item.serialNo})`).join(', ');
                        await this.env.services.popup.add(ErrorPopup, {
                            title: _t("Serial Number(s) Already Sold"),
                            body: _t(`This product with serial no has been sold please scan again:\n${bodyText}`),
                        });
                        return false;
                    }
                } catch (error) {
                    console.error("Error validating serial numbers during validation:", error);
                }
            }
        }

        return super.validateOrder(isForceValidate);
    },
});

// Patch Payment Model
patch(Payment.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
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