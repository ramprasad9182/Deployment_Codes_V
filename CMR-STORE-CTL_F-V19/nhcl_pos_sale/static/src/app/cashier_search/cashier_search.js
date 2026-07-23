/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { useState } from "@odoo/owl";

patch(SelectionPopup.prototype, {
    setup() {
        super.setup();
        this.state = useState({
            search: "",
        });
    },

    get isCashierPopup() {
        if (!this.props.list || !this.props.list.length) {
            return false;
        }
        return this.props.list.some(item => item.item && item.item.barcode !== undefined);
    },

    get filteredList() {
        const list = this.props.list || [];
        if (!this.isCashierPopup) {
            return list;
        }
        const search = (this.state.search || "").trim().toLowerCase();
        if (!search) {
            return list;
        }
        const startsWith = [];
        const includes = [];
        for (const item of list) {
            const name = (item.label || "").toLowerCase();
            if (name.startsWith(search)) {
                startsWith.push(item);
            } else if (name.includes(search)) {
                includes.push(item);
            }
        }
        return [...startsWith, ...includes];
    }
});