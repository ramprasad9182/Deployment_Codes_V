/** @odoo-module */

import { useEffect, useState } from "@odoo/owl";
import { Navbar as BaseNavbar } from "@point_of_sale/app/navbar/navbar";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

export class Navbar extends BaseNavbar {
    setup(){
        super.setup(); 
        this.state = useState({helpActive: false});
        this.env.bus.addEventListener('close_help_widget',(ev) => this.state.helpActive = ev.detail);
        const handleKeyPress = (e) => {
            if(e instanceof KeyboardEvent){
                if(e.altKey && (e.key === 'x' || e.key === 'X')){
                    this.closeSession();
                }
                else if(e.altKey && (e.key === 'c' || e.key === 'C')){
                    this.pos.closePos();
                }
                // else if(e.shiftKey && (e.key === 'm' || e.key === 'M')){
                //     this.onCashMoveButtonClick();
                // }
                else if(e.shiftKey && (e.key === 'o' || e.key === 'O')){
                    this.onTicketButtonClick();
                }
                // else if(e.altKey && e.key === 'd' && this.env.debug){
                //     this.debug.toggleWidget(); 
                // }
                // else if(e.altKey && e.key === 'f'){
                //     this.toggleProductView(); 
                // }
                else if(e.altKey && (e.key === 'p' || e.key === 'P')){
                    if (this.pos.synch.status !== "connected") {
                        this.pos.showOfflineWarning = true;
                    }
                    this.pos.push_orders({ show_error: true });
                }
                else if(e.key === 'Escape'){
                    if(this.state.helpActive){
                        this.env.bus.trigger('close_help_widget',false);
                        return;
                    }
                    if (this.pos.mainScreen.component === TicketScreen) {
                        if (this.pos.ticket_screen_mobile_pane == "left") {
                            this.pos.closeScreen();
                        } else {
                            this.pos.ticket_screen_mobile_pane = "left";
                        }
                    } else {
                        this.pos.mobile_pane = "right";
                        this.pos.showScreen("ProductScreen");
                    }
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