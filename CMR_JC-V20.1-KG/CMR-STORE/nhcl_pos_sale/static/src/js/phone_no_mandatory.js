/** @odoo-module */

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";


patch(PartnerDetailsEdit.prototype, {
    saveChanges() {
        const processedChanges = {};
        for (const [key, value] of Object.entries(this.changes)) {
            if (this.intFields.includes(key)) {
                processedChanges[key] = parseInt(value) || false;
            } else {
                processedChanges[key] = value;
            }
        }
        if (
            processedChanges.state_id &&
            this.pos.states.find((state) => state.id === processedChanges.state_id)
                .country_id[0] !== processedChanges.country_id
        ) {
            processedChanges.state_id = false;
        }

        if ((!this.props.partner.name && !processedChanges.name) || processedChanges.name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Name Is Required"),
            });
        }


        if ((!this.props.partner.name && !processedChanges.name) || processedChanges.name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Name Is Required"),
            });
        }

        if ((!this.props.partner.phone && !processedChanges.phone) || processedChanges.phone === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Phone Number Is Required"),
            });
        }
        processedChanges.id = this.props.partner.id || false;
        this.props.saveChanges(processedChanges);
    }
});