/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";

/**
 * Props:
 *  {
 *      info: {object of data}
 *  }
 */
export class LineProductInfoPopup extends AbstractAwaitablePopup {
    static template = "nhcl_pos_sale.LineProductInfoPopup";
    static defaultProps = { confirmKey: false };

    setup() {
        super.setup();
        this.pos = usePos();
        this.props.lot_ids = [];
        this.props.line.pack_lot_lines.forEach(pack => {
            const stockLot = this.pos.stock_lots_by_name[pack.lot_name];
            if (stockLot) {
                this.props.lot_ids.push(stockLot.stockLot);
            }
        });

        Object.assign(this, this.props.info);
    }
//    searchProduct(productName) {
//        this.pos.setSelectedCategoryId(0);
//        this.pos.searchProductWord = productName;
//        this.cancel();
//    }
    _hasMarginsCostsAccessRights() {
        const isAccessibleToEveryUser = this.pos.config.is_margins_costs_accessible_to_every_user;
        const isCashierManager = this.pos.get_cashier().role === "manager";
        return isAccessibleToEveryUser || isCashierManager;
    }
}
