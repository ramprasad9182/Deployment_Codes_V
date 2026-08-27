/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);

        const gstSummary = {};

        for (const tax of (result.tax_details || [])) {

            const match = (tax.name || "").match(/(\d+(?:\.\d+)?)/);
            if (!match) {
                continue;
            }

            const halfRate = parseFloat(match[1]);
            const gstRate = halfRate * 2;

            if (!gstSummary[gstRate]) {
                gstSummary[gstRate] = {
                    rate: gstRate,
                    taxable: tax.base || 0,
                    cgst: 0,
                    sgst: 0,
                };
            }

            if ((tax.name || "").includes("CGST")) {
                gstSummary[gstRate].cgst += tax.amount || 0;
            }

            if ((tax.name || "").includes("SGST")) {
                gstSummary[gstRate].sgst += tax.amount || 0;
            }
        }

        result.gst_summary = Object.values(gstSummary);

        return result;
    },
});