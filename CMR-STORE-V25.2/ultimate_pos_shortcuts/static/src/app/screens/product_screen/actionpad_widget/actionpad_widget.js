/** @odoo-module */

import { ActionpadWidget as BaseActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { useEffect } from "@odoo/owl";

export class ActionpadWidget extends BaseActionpadWidget {
    setup() {
        super.setup();
        const handleKeyPress = (e) => {
            if (e.shiftKey && (e.key === 'y' || e.key === 'Y')) {
                if (this.props.actionToTrigger) {
                    this.props.actionToTrigger();
                } else {
                    this.pos.get_order().pay();
                }
            }
        }
        useEffect(() => {
            document.body.addEventListener('keyup', handleKeyPress);
            return () => {
                document.body.removeEventListener('keyup', handleKeyPress);
            };
        });
    }
}