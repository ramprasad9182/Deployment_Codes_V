/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PaymentScreen as BasePaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useEffect, useState  } from "@odoo/owl";

export class PaymentScreen extends BasePaymentScreen {
    setup() {
        super.setup();
        this.state = useState({ orderIndex : -1});

        const handleKeyPress = (e) => {
            if(e instanceof KeyboardEvent){
                if(e.shiftKey && (e.key === 'y' || e.key === 'Y') && this.currentOrder.is_paid() && this.currentOrder._isValidEmptyOrder()){
                    this.validateOrder();
                }
                else if(e.shiftKey && (e.key === 'c' || e.key === 'C')){
                    this.pos.selectPartner();
                }
                else if(e.shiftKey && (e.key === 'i' || e.key === 'I')){
                    this.toggleIsToInvoice();
                }
                else if(e.shiftKey && (e.key === 't' || e.key === 'T') && this.pos.config.iface_tipproduct && this.pos.config.tip_product_id){
                    this.addTip();
                }
                else if(e.shiftKey && (e.key === 'b' || e.key === 'B') && this.pos.config.iface_cashdrawer){
                    this.openCashbox();
                }
//                else if(e.shiftKey && (e.key === 'd' || e.key === 'D') && this.pos.config.ship_later){
//                    this.toggleShippingDatePicker();
//                }
            }

        };

        useEffect(() => {
            document.body.addEventListener('keyup', handleKeyPress);

            return () => {
                document.body.removeEventListener('keyup', handleKeyPress);
            };
        });

    }

}

registry.category("pos_screens").remove("PaymentScreen");
registry.category("pos_screens").add("PaymentScreen", PaymentScreen);
