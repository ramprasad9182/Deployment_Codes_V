/** @odoo-module */

import { Component } from "@odoo/owl";

/**
 * props {
 *     createNewItem: callback,
 *     removeItem: callback,
 *     item: object,
 * }
 */
export class CustomEditListInput extends Component {
    static template = "nhcl_pos_sale.CustomEditListInput";

    // onKeyup(event) {
    //     if (event.key === "Enter" && event.target.value.trim() !== "") {
    //         this.props.createNewItem();
    //     }
    // }
    onKeyup(event) {
        if (event.key === "Enter" && event.target.value.trim() !== "") {
            this.props.createNewItem();
        }
    }
    onInput(event) {
        this.props.onInputChange(this.props.item._id, event.target.value);
    }

    // onInputQty(event) {
    //     this.props.onInputChangeQty(this.props.item._id, event.target.value);
    // }

    onInputQty(ev) {
        let value = ev.target.value;

        // Allow empty input while typing
        if (value === "") {
            this.props.item.qty = 0;
            return;
        }

        // Convert to number
        let qty = parseFloat(value);

        // Handle invalid numbers
        if (isNaN(qty)) {
            return;
        }

        this.props.onInputChangeQty(this.props.item._id, qty);
    }
}
