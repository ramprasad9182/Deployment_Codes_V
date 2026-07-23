/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";


export class MultiSelectionPopup extends AbstractAwaitablePopup {
    static template = "nhcl_pos_sale.MultiSelectionPopup";
    static defaultProps = {
        confirmText: _t("ADD"),
        cancelText: _t("Cancel"),
        title: _t("Select"),
        body: "",
        list: [],
        confirmKey: false,
    };

    setup() {
        super.setup();
        this.state = useState({
            selectedIds: this.props.list
                .filter((item) => item.isSelected)
                .map((item) => item.id),
        });
        this.pos = usePos();
//        this.props.total_credit_amount
    }

    selectItem(item) {
        const index = this.state.selectedIds.indexOf(item.id);

        if (index > -1) {
            this.state.selectedIds.splice(index, 1); // remove if exists
            this.props.list.filter((i) => i.id === item.id)[0].isSelected = false;
            this.props.total_credit_amount -= item.amount;
        } else {

            const credit_notes = this.props.list.filter((i) => i.isSelected);
            if (credit_notes.length > 0) {
                // const total_credit = this.props.total_credit_amount + item.amount;
                const total_credit = this.props.total_credit_amount;
                const order_total = this.pos.get_order().get_custom_totalwithtax();
                if (order_total < total_credit) {
                    return;
                }
            }

            this.state.selectedIds.push(item.id); // add if not exists
            this.props.list.filter((i) => i.id === item.id)[0].isSelected = true;
            this.props.total_credit_amount += item.amount;
        }

        // this.props.total_credit_amount = parseFloat(this.props.total_credit_amount.toFixed(2));
    }

    /**
     * We send as payload of the response the selected item.
     *
     * @override
     */
    getPayload() {
        const selectedItems = this.props.list
            .filter((item) => this.state.selectedIds.includes(item.id))
            .map((item) => item.item);
        return selectedItems;
    }
}
