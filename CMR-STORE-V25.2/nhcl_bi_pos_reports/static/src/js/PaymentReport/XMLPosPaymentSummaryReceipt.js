/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import {Component } from "@odoo/owl";

export class XMLPosPaymentSummaryReceipt extends Component {
    static template = "nhcl_bi_pos_reports.XMLPosPaymentSummaryReceipt";
    
    setup() {
        this.pos = usePos();
        
    }
    
}

