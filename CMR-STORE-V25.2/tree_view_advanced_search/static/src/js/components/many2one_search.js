
/** @odoo-module */
import { Component } from "@odoo/owl";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { Domain } from "@web/core/domain";

export class Many2OneFilter extends Component {
    static template = "Many2OneFilter";
    static components = { Many2XAutocomplete };
    static props = {
        name: String,
        relation: String,
        domain: { type: [Array, String, Function], optional: true },
        placeholder: { type: String, optional: true },
        onSelected: Function,
    };

    get many2xProps() {
        return {
            resModel: this.props.relation,
            fieldString: this.props.placeholder,
            activeActions: {},
            value: '',
            getDomain: () => {
                const rawDomain = this.props.domain;
                if (!rawDomain) return [];
                if (typeof rawDomain === "function") {
                    return rawDomain() || [];
                }
                try {
                    return new Domain(rawDomain).toList({});
                } catch (e) {
                    return Array.isArray(rawDomain) ? rawDomain : [];
                }
            },
            update: (records) => this.onSelect(records),
            placeholder: this.props.placeholder,
        };
    }

    onSearchIconClick() {
        const input = this.el?.querySelector('.o-autocomplete--input');
        if (input) {
            input.focus();
            input.click();
        }
    }

    onSelect(records) {
        const record = Array.isArray(records) ? records[records.length - 1] : records;
        if (record) {
            this.props.onSelected(record);
        }
    }
}


// /** @odoo-module */
// import { Component } from "@odoo/owl";
// import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
//
// export class Many2OneFilter extends Component {
//     static template = "Many2OneFilter";
//     static components = { Many2XAutocomplete };
//     static props = {
//         name: String,
//         relation: String,
//         placeholder: { type: String, optional: true },
//         domain: { type: [Array, String], optional: true },   // CHANGED: allow both
//         onSelected: Function,
//     };
//
//     get resolvedDomain() {
//         const d = this.props.domain;
//         if (!d) return [];
//         if (Array.isArray(d)) return d;
//         try {
//             return evaluateExpr(d);   // parses the Python-literal string safely
//         } catch {
//             return [];
//         }
//     }
//
//     get many2xProps() {
//         return {
//             resModel: this.props.relation,
//             fieldString: this.props.placeholder,
//             activeActions: {},
//             value: '',              // was: []
//             getDomain: () => this.resolvedDomain,
//             update: (records) => this.onSelect(records),
//             placeholder: this.props.placeholder,
//         };
//     }
//
//     onSearchIconClick() {
//         const input = this.el?.querySelector('.o-autocomplete--input');
//         if (input) {
//             input.focus();
//             input.click();
//         }
//     }
//
//     onSelect(records) {
//         const record = Array.isArray(records) ? records[records.length - 1] : records;
//         if (record) {
//             this.props.onSelected(record);
//         }
//     }
// }

