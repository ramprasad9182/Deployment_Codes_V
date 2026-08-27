/** @odoo-module **/

import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets"
import { rpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";
import { mount } from "@odoo/owl";
const { Component, onWillStart, useRef, onMounted, useState } = owl

class BulkTrackingAction extends Component {
   setup() {
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.actionService = useService("action");
        this.menuItems = [
          { id: 1, label: "Accounts", parent: "Master Data From HO to Stores" },
          { id: 2, label: "Products", parent: "Master Data From HO to Stores" },
          { id: 3, label: "Employees", parent: "Master Data From HO to Stores" },
          { id: 4, label: "Promotions", parent: "Master Data From HO to Stores" },
          { id: 5, label: "Business Partners", parent: "Master Data From HO to Stores" },
          { id: 6, label: "Transactions", parent: "Sync Status Of Transactions HO to All Stores" },
          { id: 7, label: "Total Batches", parent: "Sync Status Of Transactions HO to All Stores" },
          { id: 8, label: "Master Data", parent: "General Information" },
          { id: 9, label: "POS Data", parent: "General Information" },
          { id: 10, label: "Live POS Running", parent: "General Information" },

        ];
        this.state = useState({
            selected: 1,
            lastParent: '',
            today:0,
            models: [],
            pending: {
                account:'',
                tax:'',
                fiscal: '',
                partner: '',
                employee: '',
                template: '',
                category: '',
                product: '',
                users: '',
                attribute: '',
                loyalty: '',
                pendingDeliveries: ''
            },
            total: {
                account:'',
                tax: '',
                fiscal: '',
                partner: '',
                employee: '',
                template: '',
                category: '',
                product: '',
                users: '',
                attribute: '',
                loyalty: '',
                liveStore: 'Loading...',
                liveSync: 'Loading...',
                masterProcessedToday:'Loading..',
                masterNotProcessed:'Loading..',
                transactionToday: 'Loading...',
                transactionNotToday: 'Loading...',
                transactionNotProcessed: 'Loading...',
                totalBatches: 'Loading...',
                totalDeliveries: ''
            },
            processed: {
                account: 'Loading...',
                tax: 'Loading...',
                fiscal: 'Loading...',
                partner:'Loading...',
                employee:'Loading...',
                template: 'Loading...',
                category: 'Loading...',
                product: 'Loading...',
                users: 'Loading...',
                attribute: 'Loading...',
                loyalty: 'Loading...',
                processedDeliveries: 'Loading...'
            },
        });
        this._fetchData();
        this._getSelectedPendingSum();
        this._getTotalProcessedData();
        onWillStart(async () => {
            try {
                this.state.total.masterNotProcessed;
                this.state.total.masterProcessedToday;
                let result = await this.rpc("/web/action/load", { action_id: this.props.actionId });
                console.log(result);
                const domain = [['model', 'in', ['account.account','res.partner', 'product.product', 'product.template', 'product.category',
                'product.attribute','hr.employee','account.tax','res.users','loyalty.program', 'stock.picking.batch','stock.picking', 'account.fiscal.year','nhcl.ho.store.master', 'nhcl.old.store.replication.log','nhcl.transaction.replication.log']]];
                const models = await this.orm.searchRead("ir.model", domain, ["name", "id"]);
                this.state.models = models || [];

            } catch (error) {
                console.error("Failed to fetch models:", error);
                this.state.models = []; // Fallback to an empty array if there's an error
            }
        });
        this.selectMenu = (id) => {
            this.state.selected = id;
        };
   }

    _getResult(results, index, key) {
        const result = results[index];

        if (!result) {
            console.error("Missing result at index:", index);
            return 0;
        }

        if (result.status === "fulfilled") {
            return result.value?.[key] ?? 0;
        } else {
            console.error("RPC Failed:", index, result.reason);
            return 0;
        }
    }

    async _getTotalProcessedData() {
        try {
            const results = await Promise.allSettled([
                this.orm.call("account.account", "get_processed_accountToday", {}),
                this.orm.call("account.tax", "get_processed_taxToday", {}),
                this.orm.call("account.fiscal.year", "get_processed_fiscalToday", {}),
                this.orm.call("product.template", "get_processed_templateToday", {}),
                this.orm.call("product.category", "get_processed_categoryToday", {}),
                this.orm.call("res.users", "get_processed_usersToday", {}),
                this.orm.call("product.attribute", "get_processed_attributeToday", {}),
                this.orm.call("loyalty.program", "get_processed_loyaltyToday", {}),
                this.orm.call("product.product", "get_processed_productToday", {}),
                this.orm.call("hr.employee", "get_processed_employeeToday", {}),
                this.orm.call("res.partner", "get_processed_partnerToday", {}),
                this.orm.call("res.partner", "get_processed_deliveries", {}),
            ]);

            let totalPending = 0;

            results.forEach((result) => {
                if (result.status === "fulfilled") {
                    const value = Object.values(result.value)[0];
                    totalPending += Number(value) || 0;
                }
            });

            this.state.total.masterProcessedToday = totalPending;

        } catch (error) {
            console.error("Error fetching data:", error);
            return 0;
        }
    }

    async _getSelectedPendingSum() {
        try {
            const results = await Promise.allSettled([
                this.orm.call("nhcl.old.store.replication.log", "get_pending_account", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_tax", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_fiscal", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_template", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_category", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_users", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_attribute", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_loyalty", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_product", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_employee", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_partner", {}),
                this.orm.call("nhcl.transaction.replication.log", "get_pending_deliveries", {}),
            ]);

            let totalPending = 0;

            results.forEach((result) => {
                if (result.status === "fulfilled") {
                    const value = Object.values(result.value)[0];
                    totalPending += Number(value) || 0;
                }
            });

            this.state.total.masterNotProcessed = totalPending;

        } catch (error) {
            console.error("Error fetching data:", error);
            return 0;
        }
    }

    async _fetchData() {
        try {
            const results = await Promise.allSettled([
                this.orm.call("nhcl.old.store.replication.log", "get_pending_account", {}),
                this.orm.call("account.account", "get_total_account", {}),
                this.orm.call("account.account", "get_processed_account", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_tax", {}),
                this.orm.call("account.tax", "get_total_tax", {}),
                this.orm.call("account.tax", "get_processed_tax", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_fiscal", {}),
                this.orm.call("account.fiscal.year", "get_total_fiscal", {}),
                this.orm.call("account.fiscal.year", "get_processed_fiscal", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_template", {}),
                this.orm.call("product.template", "get_total_template", {}),
                this.orm.call("product.template", "get_processed_template", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_category", {}),
                this.orm.call("product.category", "get_total_category", {}),
                this.orm.call("product.category", "get_processed_category", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_users", {}),
                this.orm.call("res.users", "get_total_users", {}),
                this.orm.call("res.users", "get_processed_users", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_attribute", {}),
                this.orm.call("product.attribute", "get_total_attribute", {}),
                this.orm.call("product.attribute", "get_processed_attribute", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_loyalty", {}),
                this.orm.call("loyalty.program", "get_total_loyalty", {}),
                this.orm.call("loyalty.program", "get_processed_loyalty", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_product", {}),
                this.orm.call("product.product", "get_total_product", {}),
                this.orm.call("product.product", "get_processed_product", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_employee", {}),
                this.orm.call("hr.employee", "get_total_employee", {}),
                this.orm.call("hr.employee", "get_processed_employee", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_pending_partner", {}),
                this.orm.call("res.partner", "get_total_partner", {}),
                this.orm.call("res.partner", "get_processed_partner", {}),
                this.orm.call("nhcl.ho.store.master", "get_total_liveSync", {}),
                this.orm.call("nhcl.ho.store.master", "get_total_liveStore", {}),
                this.orm.call("nhcl.transaction.replication.log", "transactionToday", {}),
                this.orm.call("nhcl.transaction.replication.log", "transactionNotToday", {}),
                this.orm.call("nhcl.transaction.replication.log", "transactionNotProcessed", {}),
                this.orm.call("stock.picking.batch", "totalBatches", {}),
                this.orm.call("nhcl.transaction.replication.log", "PendingDeliveries", {}),
                this.orm.call("stock.picking.batch", "TotalDeliveries", {}),
                this.orm.call("nhcl.transaction.replication.log", "ProcessedDeliveries", {}),

            ]);

            this.state.pending.account = this._getResult(results, 0, "pending_account");
            this.state.total.account = this._getResult(results, 1, "total_account");
            this.state.processed.account = this._getResult(results, 2, "processed_account");

            this.state.pending.tax = this._getResult(results, 3, "pending_tax");
            this.state.total.tax = this._getResult(results, 4, "total_tax");
            this.state.processed.tax = this._getResult(results, 5, "processed_tax");

            this.state.pending.fiscal = this._getResult(results, 6, "pending_fiscal");
            this.state.total.fiscal = this._getResult(results, 7, "total_fiscal");
            this.state.processed.fiscal = this._getResult(results, 8, "processed_fiscal");

            this.state.pending.template = this._getResult(results, 9, "pending_template");
            this.state.total.template = this._getResult(results, 10, "total_template");
            this.state.processed.template = this._getResult(results, 11, "processed_template");

            this.state.pending.category = this._getResult(results, 12, "pending_category");
            this.state.total.category = this._getResult(results, 13, "total_category");
            this.state.processed.category = this._getResult(results, 14, "processed_category");

            this.state.pending.users = this._getResult(results, 15, "pending_users");
            this.state.total.users = this._getResult(results, 16, "total_users");
            this.state.processed.users = this._getResult(results, 17, "processed_users");

            this.state.pending.attribute = this._getResult(results, 18, "pending_attribute");
            this.state.total.attribute = this._getResult(results, 19, "total_attribute");
            this.state.processed.attribute = this._getResult(results, 20, "processed_attribute");

            this.state.pending.loyalty = this._getResult(results, 21, "pending_loyalty");
            this.state.total.loyalty = this._getResult(results, 22, "total_loyalty");
            this.state.processed.loyalty = this._getResult(results, 23, "processed_loyalty");

            this.state.pending.product = this._getResult(results, 24, "pending_product");
            this.state.total.product = this._getResult(results, 25, "total_product");
            this.state.processed.product = this._getResult(results, 26, "processed_product");

            this.state.pending.employee = this._getResult(results, 27, "pending_employee");
            this.state.total.employee = this._getResult(results, 28, "total_employee");
            this.state.processed.employee = this._getResult(results, 29, "processed_employee");

            this.state.pending.partner = this._getResult(results, 30, "pending_partner");
            this.state.total.partner = this._getResult(results, 31, "total_partner");
            this.state.processed.partner = this._getResult(results, 32, "processed_partner");

            this.state.total.liveSync = this._getResult(results, 33, "total_liveSync");
            this.state.total.liveStore = this._getResult(results, 34, "total_liveStore");

            this.state.total.transactionToday = this._getResult(results, 35, "transactionToday");
            this.state.total.transactionNotToday = this._getResult(results, 36, "transactionNotToday");
            this.state.total.transactionNotProcessed = this._getResult(results, 37, "transactionNotProcessed");

            this.state.total.totalBatches = this._getResult(results, 38, "totalBatches");

            this.state.pending.pendingDeliveries = this._getResult(results, 39, "PendingDeliveries");
            this.state.total.totalDeliveries = this._getResult(results, 40, "TotalDeliveries");
            this.state.processed.processedDeliveries = this._getResult(results, 41, "ProcessedDeliveries");
        } catch (error) {
            console.error("Error fetching data", error);
        }
    }

   viewAccountFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Account Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', 'ilike', 'account.account'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
   }

   viewTotalAccounts() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Accounts",
            res_model: "account.account",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }


   viewProcessedAccounts() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Accounts",
            res_model: "account.account",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewTotalTax() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Taxes",
            res_model: "account.tax",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedTax() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Taxes",
            res_model: "account.tax",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewTaxFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Tax Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', '=', 'account.tax'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }


   viewTotalEmployee() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Employee's",
            res_model: "hr.employee",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedEmployee() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Employee's",
            res_model: "hr.employee",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewEmployeeFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Employee Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', '=', 'hr.employee'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'],  [false, 'search']],
            context: {create: false}
        })
    }
   viewTemplateFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Template Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', '=', 'product.template'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
   }

   viewTotalCategory() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Category",
            res_model: "product.category",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedCategory() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Category",
            res_model: "product.category",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewTemplateTotal() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Template",
            res_model: "product.template",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewTemplateProcessed() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Template",
            res_model: "product.template",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewCategoryFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Category Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', '=', 'product.category'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }

   viewUsersTotal() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Users",
            res_model: "res.partner",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewUsersProcessed() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Users",
            res_model: "res.partner",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewUsersFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Users Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', 'ilike', 'users'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'],[false, 'search']],
            context: {create: false}
        })
   }

   viewTotalAttributes() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Attributes",
            res_model: "product.attribute",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedAttributes() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Attributes",
            res_model: "product.attribute",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewAttributeFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Attribute Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', '=', 'product.attribute'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }


   viewTotalPromotion() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Promotions",
            res_model: "loyalty.program",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedPromotion() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Promotions",
            res_model: "loyalty.program",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewPromotionFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Promotion Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', 'ilike', 'loyalty'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'],  [false, 'search']],
            context: {create: false}
        })
    }


   viewTotalVariant() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Product Variant",
            res_model: "product.product",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedVariant() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Product Variant",
            res_model: "product.product",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewVariantFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Variant Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', 'ilike', 'variant'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }

   viewTotalContact() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "All Contact's",
            res_model: "res.partner",
            domain: [],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

   viewProcessedContact() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Processed Contact's",
            res_model: "res.partner",
            domain: [['update_replication', '=', true]],
            views: [[false, 'list'], [false, 'form']],
            context: { create: false },
        });
   }

    viewContactFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Contact Failure",
            res_model: "nhcl.old.store.replication.log",
            domain: [['nhcl_model', 'ilike', 'user'],['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }

    async viewTotalSync(){
        const action = await this.orm.call(
            "nhcl.ho.store.master",
            "action_total_liveSync",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    async viewTotalLiveStore(){
        const action = await this.orm.call(
            "nhcl.ho.store.master",
            "action_total_liveStore",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    viewTransactionNotProcessed() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Failed Transactions',
            res_model: 'nhcl.transaction.replication.log',
            domain: [['nhcl_status', '=', 'failure']],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }

    async viewPendingDeliveries() {
        const action = await this.orm.call(
            "nhcl.transaction.replication.log",
            "action_pending_deliveries",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    async viewProcessedDeliveries() {
        const action = await this.orm.call(
            "nhcl.transaction.replication.log",
            "action_processed_deliveries",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    async viewTotalDeliveries() {
        const action = await this.orm.call(
            "stock.picking.batch",
            "action_total_deliveries",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }




   async viewTotalBatches() {
        const action = await this.orm.call(
            "stock.picking.batch",
            "action_total_batches",
            []
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }



    viewTransactionToday() {
        const now = new Date();
        const start = new Date(now.setHours(0, 0, 0, 0));
        const end = new Date(start);
        end.setDate(end.getDate() + 1);
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Transactions Today',
            res_model: 'nhcl.transaction.replication.log',
            domain: [
                ['nhcl_status', '=', 'success'],
                ['nhcl_date_of_log', '>=', start.toISOString()],
                ['nhcl_date_of_log', '<', end.toISOString()],
            ],
            views: [[false, 'list'], [false, 'search']],
            context: {create: false}
        })
    }
//
//    viewTransactionNotProcessedToday() {
//        const now = new Date();
//
//        // Create fresh date objects (no mutation)
//        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
//        const end = new Date(start);
//        end.setDate(end.getDate() + 1);
//
//        this.actionService.doAction({
//            type: 'ir.actions.act_window',
//            name: 'Transactions Not Processed Today',
//            res_model: 'nhcl.transaction.replication.log',
//            view_mode: 'list,form',
//            domain: [
//                ['nhcl_status', '=', 'failure'],
//                ['nhcl_date_of_log', '>=', start.toISOString()],
//                ['nhcl_date_of_log', '<', end.toISOString()],
//            ],
//            views: [[false, 'list'], [false, 'search']],
//            context: { create: false }
//        })
//    }

    async viewTransactionNotProcessedToday() {
        const action = await this.orm.call(
            "nhcl.transaction.replication.log",
            "action_failed_today",
            []
        );

        console.log("ACTION:", action); // debug

        if (action) {
            this.actionService.doAction(action);
        }
    }

}
BulkTrackingAction.template = "nhcl_ho_store_cmr_integration.BulkTracking";
registry.category("actions").add("bulk_tracking_action", BulkTrackingAction);