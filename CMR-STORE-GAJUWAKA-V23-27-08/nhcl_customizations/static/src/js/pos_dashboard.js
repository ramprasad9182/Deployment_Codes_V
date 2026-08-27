/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { MultiSelect } from "./multiselect";

const toIdArray = (arr) =>
  (arr || [])
    .map((x) => (typeof x === "object" ? x.id : x))
    .filter((v) => Number.isFinite(Number(v)))
    .map((v) => Number(v));

// keep ONE helper at module scope
function normalizeMulti(ids) {
  const set = new Set(
    (ids || [])
      .map((x) => (x && typeof x === "object" ? Number(x.id ?? x.value ?? x.res_id) : Number(x)))
      .filter((n) => Number.isFinite(n))
  );
  return set.has(0) ? [] : [...set]; // 0 = All
}

export class OwlPosDashboard extends Component {
  static template = "owl.OwlPosDashboard";
  static components = { MultiSelect };

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notify = useService("notification"); // optional

    this.menuItems = [{ id: 1, label: "CMR - STORE", parent: "Store Name" }];

    this.state = useState({
      models: [],
      selected: 1,
      recordCount: 0,
      selectedPromo: [],
      selectedCategories: [],
      period: 90,
      categorySummary: [],
      promo: [],
      categoryList: [],
    });

    onWillStart(async () => {
      try {
        await this._loadFilters();
        const domain = [['model', 'in', ['loyalty.program','product.category','pos.order.line','pos.order']]];
        this.state.models = (await this.orm.searchRead("ir.model", domain, ["name", "id"])) || [];
      } catch (e) {
        console.error("Failed to fetch models:", e);
      }
      await this.reloadSummaryFromServer();
    });
  }

  async _loadFilters() {
    try {
      const cats = await this.orm.call("product.category", "get_parent_product", [], {});
      const catOpts = cats?.parent_product || [];
      this.state.categoryList = [{ id: 0, name: "All Categories" }, ...catOpts];
      this.state.selectedCategories = [];

      const promos = await this.orm.call("loyalty.program", "get_total_promo", [], {});
      const promoOpts = promos?.promotions || [];
      this.state.promo = [{ id: 0, name: "All Promotions" }, ...promoOpts];
      this.state.selectedPromo = [];
    } catch (e) {
      console.error("Error fetching filters:", e);
      this.state.categoryList = [{ id: 0, name: "All Categories" }];
      this.state.promo = [{ id: 0, name: "All Promotions" }];
    }
  }

  /* events */
  selectMenu = (id) => { this.state.selected = Number(id); };

  onPromoChange = (ids) => {
    this.state.selectedPromo = normalizeMulti(ids);  // use top-level helper
    this.reloadSummaryFromServer();
  };

  onCategoriesChange = (ids) => {
    this.state.selectedCategories = normalizeMulti(ids); // use top-level helper
    this.reloadSummaryFromServer();
  };

  onPeriodChange = (ev) => {
    this.state.period = Number(ev.target.value) || 0;
    this.reloadSummaryFromServer();
  };

  async reloadSummaryFromServer() {
      try {
        const kwargs = {
          promo_ids: this.state.selectedPromo,
          category_ids: this.state.selectedCategories,
          period_days: this.state.period || false,
          // group_by: "root" | "parent" | "self"  // (optional) if you added that to Python
        };

        const rows = await this.orm.call(
          "loyalty.program",
          "get_category_summary_from_active_promotions",
          [],
          kwargs
        );

        this.state.categorySummary = Array.isArray(rows) ? rows : [];
        this.state.recordCount = this.state.categorySummary.length;

        // 🔎 Debug to console
        await this._debugLogActiveProgramsAndBuckets(this.state.categorySummary, kwargs);

      } catch (e) {
        console.error("Error loading summary:", e);
        this.state.categorySummary = [];
        this.state.recordCount = 0;
      }
    }

  // Build YYYY-MM-DD without timezone surprises
    _formatToday() {
      const d = new Date();
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const dd = String(d.getDate()).padStart(2, "0");
      return `${yyyy}-${mm}-${dd}`;
    }

    // Log active promotions (by date rules) and the category rows we got back
    async _debugLogActiveProgramsAndBuckets(rows, kwargs) {
      try {
        const today = this._formatToday();
        const promoDomain = [
          ["active", "=", true],
          ["|", ["date_from", "=", false], ["date_from", "<=", today]],
          ["|", ["date_to", "=", false],   ["date_to",   ">=", today]],
        ];
        if ((kwargs.promo_ids || []).length) {
          promoDomain.push(["id", "in", kwargs.promo_ids]);
        }

        const promos = await this.orm.searchRead(
          "loyalty.program",
          promoDomain,
          ["id", "name", "date_from", "date_to"]
        );

        console.log("%c[Dashboard] Filters", "color:#888");
        console.log({
          promo_ids: kwargs.promo_ids || [],
          category_ids: kwargs.category_ids || [],
          period_days: kwargs.period_days || false,
        });

        console.log("%c[Dashboard] Active promotions (by date)", "color:#0a6");
        console.table(promos.map(p => ({
          id: p.id,
          name: p.name,
          date_from: p.date_from || null,
          date_to: p.date_to || null,
        })));

        console.log("%c[Dashboard] Category buckets (from server)", "color:#06a");
        console.table((rows || []).map(r => ({
          category_id: r.category_id,
          category_name: r.category_name,
          promotion_count: r.promotion_count,
          promotion_ids: (r.promotion_ids || []).join(","),
          total_serials: r.total_serials,
          sold_serials: r.sold_serials,
          available_serials: r.available_serials,
        })));
      } catch (e) {
        console.warn("Debug logging failed:", e);
      }
    }


  // view action
  openCategoryPromotions = (ev) => {
      const raw = ev?.currentTarget?.dataset?.promos ?? "";          // e.g. "12,45,77"
      const promoIds = raw
        ? raw.split(",").map((n) => Number(n)).filter(Number.isFinite)
        : [];

      if (!promoIds.length) {
        this.notify?.add("No promotions in this category.", { type: "warning" });
        return;
      }

      if (promoIds.length === 1) {
        this.action.doAction({
          type: "ir.actions.act_window",
          name: "Promotion",
          res_model: "loyalty.program",
          res_id: promoIds[0],
          views: [[false, "form"]],
          target: "current",
        });
      } else {
        this.action.doAction({
          type: "ir.actions.act_window",
          name: "Promotions",
          res_model: "loyalty.program",
          view_mode: "tree,form",
          views: [[false, "tree"], [false, "form"]],
          domain: [["id", "in", promoIds]],
          target: "current",
        });
      }
  };

}

registry.category("actions").add("owl.pos_dashboard", OwlPosDashboard);
