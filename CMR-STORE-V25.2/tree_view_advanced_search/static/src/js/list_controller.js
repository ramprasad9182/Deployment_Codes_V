/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

patch(ListController.prototype, {
    toggleFilterRow() {
        this.env.bus.trigger("toggle_filter_row");
    },

});