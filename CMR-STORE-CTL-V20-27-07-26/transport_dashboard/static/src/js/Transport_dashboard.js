/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { MultiSelect } from "./multiselect";

const { Component, useState } = owl;
export class OwlTransportDashboard extends Component {
    static components = { MultiSelect };
    _idsFromMulti(val) {
      const out = [];
      for (const x of (val || [])) {
        let id = x;
        if (x && typeof x === "object") id = x.id ?? x.value ?? x.res_id;
        const n = Number(id);
        if (Number.isFinite(n)) out.push(n);
      }
      return out;
    }
    _normalizeForAll(val) {
      const ids = this._idsFromMulti(val);
      const positives = ids.filter((n) => n > 0);
      return positives.length ? [...new Set(positives)] : []; // [] => “All”
    }
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.menuItems = [
            { id: 1, label: "Transfer", mainParent: "Stock In Transit", subParent: "Sites" },
            { id: 2, label: "Return", mainParent: "Stock In Transit", subParent: "Sites" },
        ];
        // 1) defaults in state
        this.state = useState({
          selected: 1,
          selectedCategoryIds: [0],
          categoryOptions: [],
          loading: true,
          totalDeliveries: 0,
          totalCategories: 0,
          rows: [],
          selectedPeriod:90,
            // RETURN data
          rowsReturn: [],
          totalDeliveriesReturn: 0,
          totalCategoriesReturn: 0,
          loadingReturn: false,
          _seqR: 0,
          // RETURN filters (issuers)
          rCategoryIds: [0],
          rPeriod: 90,
          totalRecords:0,
          loadingReturn: true,
        });
        onWillStart(async () => {
            await this._loadFilterOptions();
            await Promise.all([this.fetchSummary(), this.fetchReturnSummary()]);
        });
        // If you want to be extra-safe with binding:
        this.onPeriodChange = this.onPeriodChange.bind(this);

        this.selectMenu = (id) => {
            this.state.selected = id;
        };
    }
    //filters
    async _loadFilterOptions() {
      try {
        // Categories
        const catRes = await this.orm.call("product.category", "get_parent_product", [], {});
        const catRows = catRes?.parent_product || [];
        this.state.categoryOptions = [{ id: 0, name: "All Categories" }, ...catRows];
        this.state.selectedCategoryIds = [];
      } catch (e) {
        console.error("Error fetching filters:", e);
        // Safe fallbacks
        this.state.categoryOptions = [{ id: 0, name: "All Categories" }];
      }
    }

    async onCategoriesChange(ids) {
      this.state.selectedCategoryIds = ids.includes(0) ? [0] : ids;
      await Promise.all([this.fetchSummary(), this.fetchReturnSummary()]);
    }
    async onPeriodChange(ev) {
        const raw = ev?.target?.value;
        const n = Number(raw);
        this.state.selectedPeriod = Number.isFinite(n) && n > 0 ? n : null;
        await Promise.all([this.fetchSummary(), this.fetchReturnSummary()]);
    }
    async fetchSummary() {
      this.state.loading = true;
      try {
        const selCategories = Array.isArray(this.state.selectedCategoryIds) ? this.state.selectedCategoryIds : [];

        // If the special "All" option (id=0) is present, send [] to backend (means no filter)
        const category_ids = selCategories.includes(0) ? [] : selCategories;

        const res = await this.orm.call("stock.picking", "get_transfer_dashboard_summary", [], {
          category_ids,
          group_by: "self",                                   // keep rows at the selected category level
          period_days: this.state.selectedPeriod || false,    // falsy => ignore on backend
        });
        this.state.totalDeliveries = res?.total_deliveries || 0;
        this.state.totalCategories = res?.total_categories || 0;
        this.state.rows = Array.isArray(res?.rows) ? res.rows : [];
      } catch (e) {
        console.error("fetchSummary failed:", e);
        // Optional: surface a minimal error state
        this.state.totalDeliveries = 0;
        this.state.totalCategories = 0;
        this.state.rows = [];
      } finally {
        this.state.loading = false;
      }
    }
    // RETURN
    async fetchReturnSummary() {
      const seq = ++this.state._seqR;
      this.state.loadingReturn = true;
      try {
        const category_ids = this._normalizeForAll(this.state.rCategoryIds);  // [] => all categories
        const period_days  = this.state.rPeriod || false;

        const res = await this.orm.call("stock.picking", "get_return_dashboard_summary", [{
          category_ids,
          period_days,
        }]);

        if (seq !== this.state._seqR) return; // drop stale responses

        this.state.totalDeliveriesReturn = res?.total_deliveries ?? 0;
        this.state.totalRecords          = res?.total_categories ?? 0; // or totalCategoriesReturn if you prefer
        this.state.rowsReturn            = Array.isArray(res?.rows) ? res.rows : [];
      } catch (e) {
        console.error("Return fetch failed:", e);
        this.state.totalDeliveriesReturn = 0;
        this.state.totalRecords          = 0;
        this.state.rowsReturn            = [];
      } finally {
        if (seq === this.state._seqR) this.state.loadingReturn = false;
      }
    }

    async onCategoriesChangeReturn(ids) {
      this.state.rCategoryIds = ids;
      await this.fetchReturnSummary();
    }
    onPeriodChangeReturn(ev) {
      const n = Number(ev?.target?.value);
      this.state.rPeriod = Number.isFinite(n) && n > 0 ? n : null;
      this.fetchReturnSummary();
    }
    // wait - for correct data
    async onCategoriesChange(ids) { this.state.selectedCategoryIds = ids; await this.fetchSummary(); }
}
OwlTransportDashboard.template = "owl.OwlTransportDashboard";
registry.category("actions").add("owl.transport_dashboard", OwlTransportDashboard);
