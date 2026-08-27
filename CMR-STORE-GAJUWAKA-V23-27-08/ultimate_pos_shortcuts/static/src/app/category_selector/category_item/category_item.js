/** @odoo-module */

// import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";


export class CategoryItem extends Component{
    static template = "ultimate_pos_shortcuts.CategoryItem";
    static props = {
        cate: { type: Function, optional: true },
        category : {
            type : Object, 
            shape : {
                child_id:Array,
                has_image:Boolean,
                id: Number,
                name: String,
                parent_id:Number,
                write_date:String
            },
            optional: true
        },
        isActive : { type : Boolean, optional: true }
    }

    get src() {
        let category = this.props.category;
        return category?.has_image &&
        `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`
    }
}

