/** @odoo-module */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { onMounted, useRef, useState } from "@odoo/owl";
/**
* This class represents a custom popup in the Point of Sale.
* It extends the AbstractAwaitablePopup class.
*/
export class CustomButtonPopup extends AbstractAwaitablePopup {
   static template = "nhcl_pos_sale.CustomButtonPopup";
    static defaultProps = {
        confirmText: _t("Confirm"),
        title: "",
        body: "",
    };


     setup() {
        super.setup();
        this.state = useState({ inputValue: this.props.startingValue });
        this.inputRef = useRef("input");
        onMounted(this.onMounted);
    }





    onMounted() {
        // this.inputRef.el.focus();
        setTimeout(() => {
                this.inputRef.el?.focus();
                this.inputRef.el?.select();
            }, 50);
    }
    getPayload() {
        return this.state.inputValue;
    }

    handleKeyDown(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.confirm();
        } else if (event.key === 'Escape') {
            // Prevent closing if input is empty
            if (this.state.inputValue == null || this.state.inputValue.trim() === '') {
                event.preventDefault();
            }
        }
    }

//     confirm() {
//        if (this.state.inputValue.trim() === '') {
//            // Optionally, show an error message to the user
//            // You can use a notification system to display this message
//            return; // Prevent confirmation
//        }
//        super.confirm(); // Proceed with confirmation if input is valid
//    }


}
