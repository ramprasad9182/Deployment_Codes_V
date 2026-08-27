/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

const actionRegistry = registry.category("actions");
export class EmptyPage extends Component {

}

EmptyPage.template = "nhcl_customizations.EmptyPage";
actionRegistry.add("empty_report", EmptyPage);