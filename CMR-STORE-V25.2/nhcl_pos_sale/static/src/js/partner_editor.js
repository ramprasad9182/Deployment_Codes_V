/** @odoo-module **/

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";


patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup(...arguments);

        const onKeyDown = (event) => {
            // Shortcut: Alt + S
            if ((event.altKey && event.key === 's')) {
                event.preventDefault();
                this.saveChanges();
            }
        };

        onMounted(() => {
            window.addEventListener("keydown", onKeyDown);
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", onKeyDown);
        });
    },
});