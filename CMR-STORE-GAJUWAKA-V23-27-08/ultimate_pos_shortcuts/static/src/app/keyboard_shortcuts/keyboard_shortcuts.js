/** @odoo-module */

import { Component, useState, onMounted, EventBus } from "@odoo/owl";
import { keyboard_shortcuts } from "./keyboard_shortcuts_list";


export class KeyboardShortcuts extends Component {
    static template = "ultimate_pos_shortcuts.KeyboardShortcuts";

    setup(){
        this.state = useState({ activeShortcut : 1});
        this.keyboard_shortcuts = keyboard_shortcuts;
    }

    get keyboard_shortcut(){
        const vals = this.keyboard_shortcuts
        for(let i=0;i<vals.length;i++){
            if( vals[i].id == this.state.activeShortcut) return vals[i];
        }
        return false
    }

    isActive(id){
        return id == this.state.activeShortcut;
    }

    setActiveShortcut(id,self){
        self.state.activeShortcut = id;
    }

    closeHelpWidget(){
        this.env.bus.trigger('close_help_widget',false);
    }

}