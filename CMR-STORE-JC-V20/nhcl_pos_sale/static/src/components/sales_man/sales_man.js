/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { CustomButtonPopup } from "@nhcl_pos_sale/app/custom_popup/custom_popup";

export class LineSalesmanButton extends Component {
    static template = "nhcl_pos_sale.LineSalesmanButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
    }

    async click() {

        const order = this.pos.get_order();

        const lines = order.get_orderlines().filter(
            (line) => line.select_order_line
        );

        if (lines.length < 1) {

            await this.popup.add(ErrorPopup, {
                title: _t("Sales Person"),
                body: _t("Lines are not selected, please select lines!"),
            });

            return;
        }

        const { confirmed, payload } = await this.popup.add(
            CustomButtonPopup,
            {
                startingValue: "",
                title: _t("Enter Sales Person ID"),
            }
        );

        if (!confirmed) return;

        const value = (payload || "").trim();

        if (!value) {

            await this.popup.add(ErrorPopup, {
                title: _t("Sales employee mandatory"),
                body: _t("Please Enter Sales Person Id."),
            });

            return;
        }

        let employees;

        try {

            employees = await this.orm.call(
                "hr.employee",
                "search_read",
                [[["barcode", "=", value]]],
                {
                    fields: ["id", "name", "barcode"],
                    limit: 1,
                }
            );

        } catch (error) {

            console.warn("Server error ignored:", error);
            return;
        }

        const employee = employees?.[0];

        if (!employee) {

            await this.popup.add(ErrorPopup, {
                title: _t("Invalid Employee"),
                body: _t("Please Enter Correct Employee Id."),
            });

            return;
        }

        await this.apply_salesman(employee);
    }

    async apply_salesman(employee) {

        const order = this.pos.get_order();

        const lines = order.get_orderlines().filter(
            (line) => line.select_order_line
        );

        for (const line of lines) {

            line.set_emp_no(employee.name);
            line.set_badge_id(employee.barcode);
            line.set_employee_id(employee.id);

            line.select_order_line = false;
        }
    }
}

ProductScreen.addControlButton({
    component: LineSalesmanButton,
    condition: function () {
        return true;
    },
});