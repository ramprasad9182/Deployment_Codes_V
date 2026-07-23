/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import {Component } from "@odoo/owl";

export class LocationReceipt extends Component {
    static template = "nhcl_bi_pos_reports.LocationReceipt";
    
    setup() {
        this.pos = usePos();
        
    }
    get highlight() {
        return this.props.order !== this.props.selectedOrder ? '' : 'highlight';
    }
}
