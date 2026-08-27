/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos=usePos();
        this.orm = useService("orm");
    },
    /**
     * For accessibility, pressing <space> should be like clicking the product.
     * <enter> is not considered because it conflicts with the barcode.
     *
     * @param {KeyPressEvent} event
     */
   
    async _finalizeValidation() {
        var self = this;
        var order =this.currentOrder;

        if (order.sequence_code == ""){
            if(self.env.services.pos.config.sale_receipt && self.env.services.pos.config.sale_receipt_sequence_id){
                await this.orm.call(
                    'pos.order',
                    'create_pos_receipt_sequence',
                    [0, this.currentOrder.pos_session_id],
                ).then(function(seq_code) {
                    order.set_seq_code(seq_code)
                    self.pos.db.old_uid = order.uid;
                    order.uid=seq_code;
                    order.name = _t("%s" , order.uid);
                })
                await super._finalizeValidation()
            }
            else{
                await super._finalizeValidation()
            }
        }else{
            await super._finalizeValidation()
        }
        
    },
});