/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { session } from "@web/session";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(PartnerListScreen.prototype, {
    setup() {
        super.setup(...arguments);

        this._keyHandler = (ev) => {
            // Handle Ctrl+S for Creation
            if (ev.ctrlKey && ev.key.toLowerCase() === "s") {
                ev.preventDefault();
                ev.stopPropagation();
                this.createPartner();
            }
            // Handle Alt+T for Selection
            else if (ev.altKey && ev.key.toLowerCase() === "t") {
                const partners = this.partners; // Get the currently filtered list

                if (partners && partners.length === 1) {
                    // Only stop the event if we are actually going to select a record
                    ev.preventDefault();
                    ev.stopImmediatePropagation();

                    this.clickPartner(partners[0]);
                }
                // If count != 1, we do nothing. The event "passes through"
                // so the screen stays open and the browser/Odoo behaves normally.
            }
        };

        onMounted(() => {
            // Using true (capture phase) ensures we catch the key before the search input
            window.addEventListener("keydown", this._keyHandler, true);
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", this._keyHandler, true);
        });
    },

    // willUnmount is not needed if you use Owl's onWillUnmount in setup,
    // but I have corrected your listener logic above using onMounted for Odoo 17 standards.

    createPartner() {
        const { country_id, state_id } = this.pos.company;
        let defaultValue = "";

        if (this.state.query && this.state.query.trim() !== "") {
            const searchValue = this.state.query.trim();
            const partners = this.pos.db.search_partner(searchValue);
            if (partners.length === 0) {
                defaultValue = searchValue;
            }
        }

        this.state.editModeProps.partner = {
            country_id,
            state_id,
            lang: session.user_context.lang,
        };

        if (/^[0-9]+$/.test(defaultValue)) {
            this.state.editModeProps.partner.phone = defaultValue;
        } else {
            this.state.editModeProps.partner.name = defaultValue;
        }

        this.activateEditMode();
    },
});