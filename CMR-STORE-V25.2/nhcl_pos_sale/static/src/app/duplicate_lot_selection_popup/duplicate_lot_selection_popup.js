/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";

export class DuplicateLotSelectionPopup extends AbstractAwaitablePopup {
    static template = "nhcl_pos_sale.DuplicateLotSelectionPopup";
    static defaultProps = {
        title: _t("Duplicate Lots / Barcodes Found"),
        cancelText: _t("Cancel"),
        formattedValue: "",
        lots: [],
    };

    setup() {
        super.setup();
        this.state = useState({
            selectedLot: null,
        });
    }

    selectLot(lot) {
        this.state.selectedLot = lot;
        this.confirm();
    }

    getPayload() {
        return this.state.selectedLot;
    }
}
