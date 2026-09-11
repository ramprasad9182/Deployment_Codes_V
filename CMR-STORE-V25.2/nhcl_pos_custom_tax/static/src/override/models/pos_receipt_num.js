/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

function numberToWords(num) {
    const ones = [
        "", "One", "Two", "Three", "Four", "Five",
        "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen",
        "Fifteen", "Sixteen", "Seventeen", "Eighteen",
        "Nineteen"
    ];

    const tens = [
        "", "", "Twenty", "Thirty", "Forty",
        "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
    ];

    function convert(n) {
        if (n < 20) return ones[n];

        if (n < 100) {
            return tens[Math.floor(n / 10)] + " " + ones[n % 10];
        }

        if (n < 1000) {
            return (
                ones[Math.floor(n / 100)] +
                " Hundred " +
                convert(n % 100)
            );
        }

        if (n < 100000) {
            return (
                convert(Math.floor(n / 1000)) +
                " Thousand " +
                convert(n % 1000)
            );
        }

        if (n < 10000000) {
            return (
                convert(Math.floor(n / 100000)) +
                " Lakh " +
                convert(n % 100000)
            );
        }

        return "";
    }

    return convert(Math.floor(num)).trim();
}

patch(OrderReceipt.prototype, {
    get amount_total_words() {
        return numberToWords(this.props.data.amount_total);
    },
});