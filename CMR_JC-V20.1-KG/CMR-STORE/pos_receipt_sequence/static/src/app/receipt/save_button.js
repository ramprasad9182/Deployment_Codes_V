/** @odoo-module **/

import { SaveButton } from "@point_of_sale/app/screens/product_screen/control_buttons/save_button/save_button";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(SaveButton.prototype, {
    // async onClick() {
    //     const order = this.pos.get_order();
    //
    //     if (order.sequence_code == ""){
    //         if(this.pos.config.sale_receipt && this.pos.config.sale_receipt_sequence_id){
    //             await this.pos.orm.call(
    //                 'pos.order',
    //                 'create_pos_receipt_sequence',
    //                 [0, order.pos_session_id],
    //             ).then(function(seq_code) {
    //                 order.set_seq_code(seq_code)
    //                 order.pos.db.old_uid = order.uid;
    //                 order.uid=seq_code;
    //                 order.name = _t("%s" , order.uid);
    //             })
    //         }
    //     }
    //
    //     await super.onClick(...arguments);
    // }
});