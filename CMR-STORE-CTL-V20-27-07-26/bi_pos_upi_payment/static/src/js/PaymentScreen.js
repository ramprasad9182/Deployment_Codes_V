/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { UPIQRPopup } from "@bi_pos_upi_payment/js/UPIQRPopup";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    },
    async upiNewPaymentLine(paymentMethod) {
        var self = this;
        let upiMethod = this.pos.db.pos_upi_payments;
        var method = []
        for (var data of paymentMethod.pos_upi_payment_ids){
           for(var data1 in upiMethod){
                if (data  == upiMethod[data1].id){
                    method.push(upiMethod[data1])
                }
            }
        }
        let order = self.currentOrder;
        let amount = order.get_due();
        let currency = self.pos.config.currency_id[1];
        if (paymentMethod.upi) {
            await self.pos.popup.add(UPIQRPopup, {
                'upi_name': method[0].upi_name,
                'upi_vpa': method[0].upi_vpa,
                'upi_id': method[0].id,
                'name': method[0].name,
                'amount': amount,
                'paymentMethod': paymentMethod,
                'currency': currency,
            });

        } else {
            let result = self.currentOrder.add_paymentline(paymentMethod);
            if (result) {
                self.pos.numberBuffer.reset();
                return true;
            } else {
                self.pos.popup.add(ErrorPopup, {
                    title: _t('Error'),
                    body: _t('There is already an electronic payment in progress.'),
                });
                return false;
            }
        }
    },
    get upi_payments() {
        let methods = this.pos.db.pos_upi_payments;
        let upi_methods = [];
        $.each(methods, function(i, upi) {
            if (upi.visible_in_pos) {
                upi_methods.push(upi)
            }
        });
        return upi_methods;
    },
    get upi_image() {
        var self = this;
        return `/web/image?model=self.pos.upi.payment&field=upi_image&id=${self.upiMethod.id}&unique=1`;
    }
})
