/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";


patch(Order.prototype, {

    setup() {
        super.setup(...arguments);

        if(this.pos.config.default_partner_id){
            var default_customer = this.pos.config.default_partner_id[0];
            var partner = this.pos.db.get_partner_by_id(default_customer);
            this.set_partner(partner);
        }
        },	
});


