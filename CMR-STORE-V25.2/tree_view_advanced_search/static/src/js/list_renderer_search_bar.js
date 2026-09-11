/** @odoo-module */
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { DateRange } from "./components/date_range";
import { Many2OneFilter } from "./components/many2one_search";
import { PurchaseDashBoardRenderer } from "@purchase/views/purchase_listview";
import { AccountMoveUploadListRenderer } from "@account/components/bills_upload/bills_upload";
import { useState } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";



/*
let PurchaseDashBoardRenderer;
try {
    PurchaseDashBoardRenderer = require("@purchase/views/purchase_listview").PurchaseDashBoardRenderer;
} catch (e) {}

let AccountMoveUploadListRenderer;
try {
    AccountMoveUploadListRenderer = require("@account/components/bills_upload/bills_upload").AccountMoveUploadListRenderer;
} catch (e) {}
*/

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.domain = [],
            this.selectedItem = null
        this.selectedMany2oneIds = {};
        this.filterRowState = useState({show: false,});

        useBus(this.env.bus, "toggle_filter_row", () => {
            this.filterRowState.show = !this.filterRowState.show;
        });
    },

    // toggleFilterRow() {
    //     this.filterRowState.show = !this.filterRowState.show;
    // },
    // Function for search while clicking "ENTER BUTTON"
    _onKeyPress(ev, name, obj) {
        if (ev.key === "Enter" && ev.currentTarget.value.trim() !== '') {
            obj.addTag(ev.currentTarget.value.trim(), name);
            ev.currentTarget.value = '';
            const Domain = obj._getInputValueAndDomain(ev, name);
            obj._getResultData(Domain);
        }
    },
    // Function to add search data in a pill structure
    addTag(tagText, name) {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = tagText;
        const removeButton = document.createElement('i');
        removeButton.className = 'fa fa-close';
        removeButton.addEventListener('click', () => this.removeTag(tag, name));
        tag.appendChild(removeButton);
        document.getElementById(name + 'Container').appendChild(tag);
    },
    // Search function to filter, based on the input
    _onClick_search: function (ev, name) {
        this.addTag(ev.target.previousElementSibling.value, name);
        ev.target.previousElementSibling.value = '';
        const Domain = this._getInputValueAndDomain(ev, name);
        this._getResultData(Domain);
    },
    // To set the domain for filter based on the user input
    _getInputValueAndDomain(ev, name) {
        const tags = ev.currentTarget.closest('.search-input').querySelectorAll('.tag');
        const inputValues = [];
        tags.forEach(tag => {
            inputValues.push(tag.textContent);
        });
        var Domain = []
        if (inputValues.length > 1) {
            for (let input = 0; input < inputValues.length; input++) {
                if (input != inputValues.length - 1) {
                    Domain.splice(input, 0, '|');
                }
                Domain.push([name, 'ilike', inputValues[input]])
            }
        }
        else {
            Domain.push([name, 'ilike', inputValues[0]])
        }
        return Domain;
    },
    //Passing the domain to filter
    _getResultData(Domain) {
        if (((this.domain).length == 0) && (this.__owl__.parent.parent.props.domain[0] != null)) {
            this.domain = this.__owl__.parent.parent.props.domain;
        }
        this.env.searchModel.clearQuery();
        var result_domain = this.updateDomain(this.domain, Domain);
        this.domain = result_domain;
        this.env.searchModel.splitAndAddDomain(result_domain);
    },
    // To set all the Domains
    updateDomain(default_domain, new_domain) {
        var result_domain = default_domain
        for (let new_index = 0; new_index < new_domain.length; new_index++) {
            for (let index = 0; index < default_domain.length; index++) {
                if (new_domain[new_index][0] == default_domain[index][0]) {
                    default_domain.splice(index, 1);
                    index--;
                }
            }
        }
        if (new_domain.length !== 0) {
            for (let i = 0; i < new_domain.length; i++) {
                result_domain.push(new_domain[i]);
            }
        }
        return result_domain;
    },
    // To Remove the added filter
    removeTag(tag, name) {
        let tagValue = tag.childNodes[0].nodeValue.trim();
        const Domain = [name, 'ilike', tagValue]
        let found = false;
        this.domain = this.domain.filter(function (domain) {
            if (JSON.stringify(domain) == JSON.stringify(Domain)) {
                found = true;
                return false;
            }
            return true;
        });
        if (found) {
            const index = this.domain.indexOf("|");
            if (index !== -1) {
                this.domain.splice(index, 1);
            }
        }
        this.env.searchModel.clearQuery();
        this.env.searchModel.splitAndAddDomain(this.domain);
        tag.remove();
    },
    // Function for filter in selection field, to add and remove the filter
    changeStateSelection(name, value) {
        const domain = [name, '=', value]
        const Domain = [domain]
        if (value == this.selectedItem) {
            // If value equals to selecteditem then want to remove the filter.
            this.selectedItem = null
            this.domain = this.domain.filter(item => JSON.stringify(item) !== JSON.stringify(domain));
            this.env.searchModel.clearQuery();
            this.env.searchModel.splitAndAddDomain(this.domain);
        }
        else {
            this.selectedItem = value;
            this._getResultData(Domain);
        }
    },
    // Function for filter in Date field
    changeDate(name, date) {
        if (date.from && date.to) {
            var Domain = ['&', [name, '>=', date.from], [name, '<=', date.to]]
        }
        if (date.from && date.to == false) {
            var Domain = [[name, '>=', date.from]]
        }
        if (date.from == false && date.to) {
            var Domain = [[name, '<=', date.to]]
        }
        this._getResultData(Domain);
    },

    // NEW — called from Many2OneFilter's onSelected prop
    addMany2oneTag(name, record) {
        if (!this.selectedMany2oneIds[name]) {
            this.selectedMany2oneIds[name] = [];
        }
        if (this.selectedMany2oneIds[name].some(r => r.id === record.id)) {
            return; // already added
        }
        this.selectedMany2oneIds[name].push({ id: record.id, display_name: record.display_name });

        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = record.display_name;
        const removeButton = document.createElement('i');
        removeButton.className = 'fa fa-close';
        removeButton.addEventListener('click', () => this.removeMany2oneTag(tag, name, record.id));
        tag.appendChild(removeButton);
        document.getElementById(name + 'Container').appendChild(tag);

        this._applyMany2oneDomain(name);
    },

    // NEW
    removeMany2oneTag(tag, name, id) {
        this.selectedMany2oneIds[name] = (this.selectedMany2oneIds[name] || []).filter(r => r.id !== id);
        tag.remove();
        this._applyMany2oneDomain(name);
    },

    // NEW — rebuilds the domain leaf for this field only, using 'in' on ids
    _applyMany2oneDomain(name) {
        if (this.domain.length == 0 && this.__owl__.parent.parent.props.domain[0] != null) {
            this.domain = this.__owl__.parent.parent.props.domain;
        }
        this.domain = this.domain.filter(d => !(Array.isArray(d) && d[0] === name));
        const ids = (this.selectedMany2oneIds[name] || []).map(r => r.id);
        if (ids.length) {
            this.domain.push([name, 'in', ids]);
        }
        this.env.searchModel.clearQuery();
        this.env.searchModel.splitAndAddDomain(this.domain);
    },
})
ListRenderer.components = { ...ListRenderer.components, DateRange, Many2OneFilter }


if (PurchaseDashBoardRenderer) {
    PurchaseDashBoardRenderer.components = { ...PurchaseDashBoardRenderer.components, DateRange, Many2OneFilter };
}

if (AccountMoveUploadListRenderer) {
    AccountMoveUploadListRenderer.components = { ...AccountMoveUploadListRenderer.components, DateRange, Many2OneFilter };
}
