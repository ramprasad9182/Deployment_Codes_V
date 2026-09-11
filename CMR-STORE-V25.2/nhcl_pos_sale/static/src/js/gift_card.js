/** @odoo-module **/
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";


patch(PaymentScreen.prototype, {

    setup() {
        super.setup(...arguments);

        setTimeout(() => {
            this.autoApplyGiftVoucher();
        }, 0);
    },

    autoApplyGiftVoucher() {
        const order = this.currentOrder;
        if (!order) return;

        // detect coupon / gift voucher line
        const couponLine = order.get_orderlines().find(line =>
            line.coupon_id > 0 && line.price < 0
        );
        if (!couponLine) return;
        const paymentMethod = this.pos.payment_methods.find(
            p => p.name === "Gift Voucher"
        );
        if (!paymentMethod) return;
        const alreadyExists = order.paymentlines.find(
            p => p.payment_method.id === paymentMethod.id
        );
        if (!alreadyExists) {
            const paymentLine = order.add_paymentline(paymentMethod);
            paymentLine.set_amount(Math.abs(couponLine.price));
        }
    },

});