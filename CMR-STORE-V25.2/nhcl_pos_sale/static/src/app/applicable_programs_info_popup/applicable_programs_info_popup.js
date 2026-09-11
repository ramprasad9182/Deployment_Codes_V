/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";

/**
 * Props:
 *  {
 *      info: {object of data}
 *  }
 */
export class ApplicableProgramsInfoPopup extends AbstractAwaitablePopup {
    static template = "nhcl_pos_sale.ApplicableProgramsInfoPopup";
    static defaultProps = { confirmKey: false };

    setup() {
        super.setup();
        this.pos = usePos();
        this.state = useState({
            applicable_rewards: this.props.info,
        });
    }
}
