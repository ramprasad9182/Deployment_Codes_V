/** @odoo-module */

import { Component, useState, onMounted, EventBus } from "@odoo/owl";
import { CategoryItem } from "./category_item/category_item";
import { useBus, useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";


export class CategorySelector extends Component {
    static template = "ultimate_pos_shortcuts.CategorySelector";
    static components = { CategoryItem }
    setup(){
        this.pos = usePos();
    }

    get categoryList(){
        let category_by_id = this.pos.db.category_by_id;
        return Object.keys(category_by_id).map((key) => category_by_id[key])
    }
    get categoryToShowList(){
        let categoryList = this.categoryList;
        let activeIndex = this.categoryActiveIndex;
        let categoryCount = categoryList.length;
    
        if (activeIndex === -1) {
            // No active category selected, return empty list
            return [];
        }
    
        const beforeActiveIndex = (activeIndex - 1 + categoryCount) % categoryCount;
        const afterActiveIndex = (activeIndex + 1) % categoryCount;
    
        // Extract the category items
        const beforeActiveCategory = categoryList[beforeActiveIndex];
        const activeCategory = categoryList[activeIndex];
        const afterActiveCategory = categoryList[afterActiveIndex];
    
        // Create the list to show with an item before and after the active item
        return [beforeActiveCategory, activeCategory, afterActiveCategory];
    }
    get categoryActiveIndex(){
        let selectedId = this.pos.selectedCategoryId;
        let categoryList = this.categoryList;
        for(let i=0;i < categoryList.length;i++){
            if(categoryList[i].id === selectedId) return i;
        }
        return -1;
    }
    isActive(category){
        return category.id === this.pos.selectedCategoryId;
    }

}