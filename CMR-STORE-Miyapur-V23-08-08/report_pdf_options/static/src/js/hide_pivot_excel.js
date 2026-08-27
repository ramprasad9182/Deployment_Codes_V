/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

patch(PivotRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        this.user = useService("user");

        onWillStart(async () => {
            this.canDownloadPivot = await this.user.hasGroup(
                "base.group_allow_export"
            );
        });
    },

    async onDownloadButtonClicked() {
        if (!this.canDownloadPivot) {
            return;
        }
        return super.onDownloadButtonClicked(...arguments);
    },
});