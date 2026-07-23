/** @odoo-module */

import { Transition } from "@web/core/transition";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { ErrorHandler } from "@web/core/utils/components";
import { Navbar } from "@ultimate_pos_shortcuts/app/navbar/navbar";
import { Chrome as BaseChrome } from "@point_of_sale/app/pos_app";
import { CategorySelector } from "./category_selector/category_selector";
import { useState, useEffect, EventBus } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { KeyboardShortcuts } from "./keyboard_shortcuts/keyboard_shortcuts";


/**
 * Chrome is the root component of the PoS App.
 */
export class Chrome extends BaseChrome {
    static components = { Transition, MainComponentsContainer, ErrorHandler, Navbar, CategorySelector, KeyboardShortcuts };
    static template = "ultimate_pos_shortcuts.Chrome";

    setup(){
        super.setup();
        this.state = useState({categorySelectorActive:false,helpActive: false});
        this.env.bus.addEventListener('close_help_widget',(ev) => this.state.helpActive = ev.detail);
        const handleKeyDown = (ev) => {
            if(ev instanceof KeyboardEvent){
//                if(ev.ctrlKey && (ev.key === 'A' || ev.key === 'a')){
//                    this.state.categorySelectorActive = true;
//                    this.env.bus.trigger('activate_category_selector', true);
//
//                }
//                else if(ev.ctrlKey && ev.key === '?'){
//                    this.env.bus.trigger('close_help_widget',true);
//                }
                if(ev.ctrlKey && ev.key === '?'){
                    this.env.bus.trigger('close_help_widget',true);
                }
            }
        }
        const handleKeyUp = (ev) => {
            if(ev instanceof KeyboardEvent){
                if(this.state.categorySelectorActive && (ev.key === 'A' || ev.key === 'a')){
                    this.state.categorySelectorActive = false;
                    this.env.bus.trigger('activate_category_selector', false);

                }
                else if(ev.key === 'ArrowLeft' && this.state.categorySelectorActive){
                    let i = this.categoryActiveIndex
                    i--;
                    if(i < 0){
                        i = this.categoryList.length -1;
                    }
                    let category = this.categoryList[i];
                    this.pos.setSelectedCategoryId(category.id);
                }
                else if(ev.key === 'ArrowRight' && this.state.categorySelectorActive){
                    let i = this.categoryActiveIndex
                    i++;
                    if(i > this.categoryList.length -1){
                        i = 0;
                    }
                    let category = this.categoryList[i];
                    this.pos.setSelectedCategoryId(category.id);
                }
            }
        }
        useEffect(()=>{
            document.body.addEventListener('keydown',handleKeyDown);
            document.body.addEventListener('keyup',handleKeyUp);
            return () => {
                document.body.removeEventListener('keydown',handleKeyDown);
                document.body.removeEventListener('keyup',handleKeyUp);
            }

        });
    }
    get categoryList(){
        let category_by_id = this.pos.db.category_by_id;
        return Object.keys(category_by_id).map((key) => category_by_id[key])
    }


    
    get categoryActiveIndex(){
        let selectedId = this.pos.selectedCategoryId;
        let categoryList = this.categoryList;
        for(let i=0;i < categoryList.length;i++){
            if(categoryList[i].id === selectedId) return i;
        }
        return -1;
    }
}