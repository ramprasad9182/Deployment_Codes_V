/** @odoo-module */
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class UPIQRPopup extends AbstractAwaitablePopup {
    static template = "bi_pos_upi_payment.UPIQRPopup";
    setup() {
        super.setup();
        this.pos = usePos();
    }
    get qrcode() {
        var self = this;
        const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter()
        var upi = "upi://pay?pa=" + self.props.upi_vpa + "&pn=" + self.props.upi_name + "&am=" + self.props.amount + "&cu=" + self.props.currency;
        let qr_code_svg = new XMLSerializer().serializeToString(codeWriter.write(upi, 600, 600));
        var qrcode = "data:image/svg+xml;base64," + window.btoa(qr_code_svg);
        return qrcode
    }
    
    async confirm_payment() {
        var self = this;
        var current_order = self.env.services.pos.get_order();
        let result = current_order.add_paymentline(this.props.paymentMethod);
        if (result) {
            var self = this;
            self.pos.numberBuffer.reset();
            self.cancel();
            return true;
        } else {
            var self = this;
            self.pos.popup.add(ErrorPopup, {
                title: _t('Error'),
                body: _t('There is already an electronic payment in progress.'),
            });
            self.cancel();
            return false;
        }
    }
    get upi_image() {
        var self = this;
        return `/web/image?model=self.pos.upi.payment&field=upi_image&id=${self.props.upi_id}&unique=1`;
    }
}

