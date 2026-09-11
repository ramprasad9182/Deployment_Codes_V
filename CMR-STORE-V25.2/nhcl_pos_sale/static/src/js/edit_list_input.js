/** @odoo-module **/

import { EditListInput } from "@point_of_sale/app/store/select_lot_popup/edit_list_input/edit_list_input";
import { patch } from "@web/core/utils/patch";

patch(EditListInput.prototype, {
    /**
     * @override
     */
    onKeyup(event) {
        // By leaving this body empty (or just not calling the original),
        // you effectively disable the "Enter to create" logic.

        // If you want to keep other potential logic but specifically
        // kill the 'Enter' behavior, you could do:
        if (event.key === "Enter") {
            return;
        }

        // If there was original logic you wanted to keep,
        // you would call super.onKeyup(event) here.
    },
});