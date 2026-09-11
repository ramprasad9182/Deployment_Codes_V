/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useAutofocus } from "@web/core/utils/hooks";
import {useRef, useState} from "@odoo/owl";

/**
 * Props:
 *  {
 *      info: {object of data}
 *  }
 */
export class SalesPersonsInfoPopup extends AbstractAwaitablePopup {
    static template = "nhcl_pos_sale.SalesPersonsInfoPopup";
    static defaultProps = { confirmKey: false };

    setup() {
        super.setup();
        this.pos = usePos();
        this.searchWordInputRef = useRef("search-word-input-partner");
        useAutofocus({refName: 'search-word-input-partner'});
        this.state = useState({
            query: null,
            salespersons: this.props.info,
            filtered_salespersons: this.props.info,
            previousQuery: "",
            currentOffset: 0,
        });
    }

    async _onPressEnterKey() {
        if (!this.state.query) {
            return;
        }
        this.state.filtered_salespersons = this.state.salespersons.filter(sp =>
            this._partner_search_string(sp).toLowerCase().includes(this.state.query.toLowerCase())
        );
    }

    async updatePartnerList(event) {
        this.state.query = event.target.value;
        this.state.filtered_salespersons = this.state.salespersons.filter(sp =>
            this._partner_search_string(sp).toLowerCase().includes(this.state.query.toLowerCase())
        );
    }

    _clearSearch() {
        this.searchWordInputRef.el.value = "";
        this.state.query = "";
        this.state.filtered_salespersons = this.state.salespersons;
    }

    _partner_search_string(salesperson) {
        var str = salesperson.name || "";
        str += "|" + (salesperson.barcode || "");
        str = "" + str.replace(":", "").replace(/\n/g, " ") + "\n";
        return str;
    }
}
