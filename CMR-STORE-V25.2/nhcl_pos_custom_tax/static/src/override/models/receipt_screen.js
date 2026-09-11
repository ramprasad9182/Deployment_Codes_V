/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { useService } from "@web/core/utils/hooks";

patch(PaymentScreen.prototype, {

    setup() {
        super.setup(...arguments);
        this.printer = useService("printer");
    },

    async validateOrder(isForceValidate) {

        // capture order BEFORE validation
        const order = this.pos.get_order();

        // disable odoo auto print
        const originalPrinter = this.printer.print;
        let validationError = null;

        try {
            this.printer.print = async () => true;
            // validate order
            await super.validateOrder(isForceValidate);
        } catch (error) {
            validationError = error;
        } finally {
            // ALWAYS restore printer, even if validation fails or throws an error!
            this.printer.print = originalPrinter;
        }

        if (validationError) {
            throw validationError;
        }

        // If validation failed, the active screen will still be PaymentScreen (this.constructor)
        if (this.pos.mainScreen.component === this.constructor) {
            return false;
        }

        // Export data AFTER validation, so date_order is updated by Odoo's core validation flow
        const data = order.export_for_printing();
        data.name = order.name;

        // ONLY ONE PRINT (merged receipt)
        await this.printer.print(
            OrderReceipt,
            {
                data: { ...data },
                formatCurrency: this.env.utils.formatCurrency,
            },
            { webPrintFallback: true }
        );

        return true;
    },

});