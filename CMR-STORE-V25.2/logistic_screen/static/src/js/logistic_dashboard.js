/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState } = owl;

export class LogisticDashboard extends Component {

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            // Status bars 1.2
            status: { delivered: 0, in_transit: 0, delayed: 0},
            loadingStatus: true,
            // state additions
            draft: {today: 0, week: 0, month: 0},  // upcoming (state=draft) 3.1
            done: { today: 0, week: 0, month: 0},  // delivered (state=done)1.1
            loadingDelivery: true,
            // partialDelivered 2.1
            partialDelivered: 0,
            loadingPartialDelivered: true,
            // top unopened divisions 2.2
             unopenedDivision: { total: 0, items: [] },
             loadingUnopenedDivision: true,
             // topProducts 3.2
            topProducts: { total: 0, max: 0, items: [] },
            loadingTopProducts: true,
            // top divisions - bales 3.3
             unopenedDivisionBales: { total: 0, items: [] },
             loadingUnopenedDivisionBales: true,
            // openParcel 2.3
            openParcel: { draft: 0, done: 0, total: 0 },
            loadingOpenParcel: true,
            // 1) state additions (in your useState initial object)
            openParcel: { draft: 0, done: 0},
            loadingOpenParcel: true,
        });
        // % of total (for horizontal bars)
        this.pct = (n, total) => {
          const t = Number(total || 0), v = Number(n || 0);
          if (!t) return 0;
          return Math.max(0, Math.min(100, Math.round((v * 100) / t)));
        };
        // height % vs max (for columns)
        this.hPct = (v) => {
          const m = Number(this.state.topProducts.max || 0);
          const n = Number(v || 0);
          if (!m) return 0;
          return Math.round((n * 100) / m);
         };
        onWillStart(async () => {
            this.fetchDeliveryPeriods(),
            this.fetchUpcomingDeliveryPeriods(),
            this.fetchPartialDelivered(),
            this.fetchOpenParcelCounts(),
            this.loadDeliveryStatus(),
            this.loadUnopenedDivision(),
            this.loadTopProducts(),
            this.loadPendingDivisionBales()
        });
    }

    async fetchDeliveryPeriods(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_upcoming_counts",
          [],
          { kwargs: filters }
        );
        const dn = (res && res.done)  || {};
        this.state.done = {
          today: Number(dn.today || 0),
          week:  Number(dn.week  || 0),
          month: Number(dn.month || 0),
        };
      } catch (e) {
        console.error("Delivery period counts fetch failed:", e);
        this.notification.add("Failed to load Upcoming/Delivered counts.", { type: "danger" });
      } finally {
        this.state.loadingDelivery = false;
      }
    }

    async fetchUpcomingDeliveryPeriods(filters = {}) {
      try {
        this.state.loadingDelivery = true;
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_upcoming_counts",
          [],
          { kwargs: filters }
        );
        const d = (res && res.draft) || {};
        this.state.draft = {
          today: Number(d.today || 0),
          week:  Number(d.week  || 0),
          month: Number(d.month || 0),
        };
      } catch (e) {
        console.error("Upcoming counts fetch failed:", e);
        this.notification.add("Failed to load Upcoming counts.", { type: "danger" });
      } finally {
        this.state.loadingDelivery = false;
      }
    }

    async fetchPartialDelivered(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_partial_delivered_lr",
          [],
          { kwargs: filters }
        );
        const v = (res && res.count) || 0;
        this.state.partialDelivered = Number(v);
      } catch (e) {
        console.error("Partial delivered fetch failed:", e);
        this.notification.add("Failed to load Partial Delivered LRs.", { type: "danger" });
      } finally {
        this.state.loadingPartialDelivered = false;
      }
    }

    async loadDeliveryStatus() {
        this.state.loadingStatus = true;
        const res = await this.orm.call(
            'logistic.screen.data',
            'get_delivery_status_counts',
            [],
            {}
        );
        const dn = (res && res.status)  || {};
        this.state.status = {
            delivered: Number(dn.delivered || 0),
            in_transit: Number(dn.in_transit || 0),
            delayed: Number(dn.delayed || 0),
         };
        this.state.loadingStatus = false;
    }

    async fetchOpenParcelCounts(filters = {}) {
      try {
        this.state.loadingOpenParcel = true;
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_bales_against_lr",
          [],
          { kwargs: filters }
        );
        this.state.openParcel = {
            done: res?.open || 0,
            draft: res?.unopen || 0,
        };
      } catch (e) {
        console.error("Open parcel counts fetch failed:", e);
        this.notification.add("Failed to load Open Parcel counts.", { type: "danger" });
      } finally {
        this.state.loadingOpenParcel = false;
      }
    }

    async fetchDeliveryPeriods(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_delivery_period_counts",
          [],
          { kwargs: filters }
        );
        const d = (res && res.draft) || {};
        const dn = (res && res.done)  || {};
        this.state.done = {
          today: Number(dn.today || 0),
          week:  Number(dn.week  || 0),
          month: Number(dn.month || 0),
        };
      } catch (e) {
        console.error("Delivery period counts fetch failed:", e);
        this.notification.add("Failed to load Upcoming/Delivered counts.", { type: "danger" });
      } finally {
        this.state.loadingDelivery = false;
      }
    }

    async loadUnopenedDivision() {
        try {
            const res = await this.orm.call(
                "logistic.screen.data",
                "get_unopened_division_counts",
                [],
                {}
            );
            this.state.unopenedDivision = {
                total: res?.total || 0,
                items: res?.items || []
            };
        } catch (error) {
            console.error("Error loading unopened division:", error);
            this.state.unopenedDivision = { total: 0, items: [] };
        }
    }
    async openDivisionDeliveries(divisionName) {
        const pickingIds = await this.orm.call(
            "logistic.screen.data",
            "get_pickings_by_division",
            [divisionName]
        );
        const ids = Array.isArray(pickingIds) ? pickingIds : [];
        if (!ids.length) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Receipts - ${divisionName}`,
            res_model: "stock.picking",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: [["id", "in", ids]],
        });
    }
    async loadTopProducts() {
        this.state.loadingTopProducts = true;
        const res = await this.orm.call(
            "logistic.screen.data",
            "get_top_delivered_products",
            [],
            {}
        );
        this.state.topProducts = {
            total: res?.total || 0,
            max: res?.max || 1,
            items: res?.items || []
        };
        this.state.loadingTopProducts = false;
    }
    async openTopProduct(parentName) {
        const ids = await this.orm.call(
            "logistic.screen.data",
            "get_pickings_by_product_parent",
            [parentName]
        );
        const safeIds = Array.isArray(ids) ? ids : [];
        if (!safeIds.length) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Receipts - ${parentName}`,
            res_model: "stock.picking",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: [["id", "in", safeIds]],
        });
    }
    async loadPendingDivisionBales() {
        const res = await this.orm.call(
            "logistic.screen.data",
            "get_pending_grc_division_bales",
            [],
            {}
        );
        this.state.unopenedDivisionBales = {
            items: res?.items || []
        };
    }
    barPx(value, maxHeight = 140) {
        const max = this.state.topProducts.max || 1;
        return Math.max((value / max) * maxHeight, 6);
    }
    fmtINR(n) {
        return Number(n || 0).toLocaleString('en-IN',{
                style: 'currency', currency: 'INR', maximumFractionDigits: 0
        });
    }
    fmt(n) {
        return Number(n || 0).toLocaleString();
    }
    barPx(count, chartH = 140) {
      const max = Number(this.state.topProducts.max || 0);
      const c = Number(count || 0);
      if (!max) return 4;                        // tiny stub if no data
      return Math.max(4, Math.round((c * chartH) / max));
    }
    // helper to dispatch the action (modern service with fallback)
    _doAction = (action) => {
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        return actionSvc.doAction(action);
      } else if (this.trigger) {
        return this.trigger("do-action", action);
      } else {
        return Promise.resolve();
      }
    };
    async openOpenParcels() {
        await this._openByLR('open');
    }
    async openUnopenParcels() {
        await this._openByLR('unopen');
    }
    async _openByLR(type) {
        const res = await this.orm.call(
            "logistic.screen.data",
            "get_pickings_by_lr_state",
            [type]
        );
        const safeIds = Array.isArray(res) ? res : [];
        if (!safeIds.length) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: type === 'open' ? "Open LR" : "Unopen LR",
            res_model: "stock.picking",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            target: "current",
            domain: [["id", "in", safeIds]],
        });
    }
    // Draft (upcoming)
    _openDelivered(domain, name) {
        const baseDomain = [
            ['stock_picking_type', '=', 'receipt'],
        ];
        this._doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: 'stock.picking',
            views: [[false, 'list'], [false, 'form']],
            domain: [...baseDomain, ...domain],
            target: 'current',
        });
    }
    openDelayed = async () => {
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Delayed Receipts',
            res_model: 'stock.picking',
            view_mode: 'list,form',
            domain: [
                ['stock_picking_type', '=', 'receipt'],
                ['state', '=', 'assigned'],
                ['is_delayed', '=', true],
            ],
        });
    };
    openDraftToday = () => {
        const start = new Date();
        start.setHours(0, 0, 0, 0);
        const end = new Date(start);
        end.setDate(end.getDate() + 1);
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'assigned'],
            ['is_received', '=', false],
            ['create_date', '>=', start.toISOString()],
            ['create_date', '<', end.toISOString()],
       ];
        this._openDelivered(domain, "Up Coming Delivery -Of Today");
    };
    openDraftWeek = () => {
        const today = new Date();
        const start = new Date(today);
        start.setDate(today.getDate() - 6);
        start.setHours(0, 0, 0, 0);
        const end = new Date(today);
        end.setDate(end.getDate() + 1);
        end.setHours(0, 0, 0, 0);
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'assigned'],
            ['is_received', '=', false],
            ['create_date', '>=', start.toISOString()],
            ['create_date', '<', end.toISOString()],
        ];
        this._openDelivered(domain, "Up Coming Delivery - Of One Week");
    };
    openDraftMonth  = () => {
        const today = new Date();
        const start = new Date(today);
        start.setDate(today.getDate() - 29);
        start.setHours(0, 0, 0, 0);
        const end = new Date(today);
        end.setDate(end.getDate() + 1);
        end.setHours(0, 0, 0, 0);
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'assigned'],
            ['is_received', '=', false],
            ['create_date', '>=', start.toISOString()],
            ['create_date', '<', end.toISOString()],
        ];
        this._openDelivered(domain, "Delivered — Of One Month");
    };
    openDoneToday = () => {
        const start = new Date();
        start.setHours(0, 0, 0, 0);
        const end = new Date(start);
        end.setDate(end.getDate() + 1); // next day start
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'done'],
            ['date_done', '>=', start.toISOString()],
            ['date_done', '<', end.toISOString()],
        ];
        this._openDelivered(domain, "Delivered — Today");
    };
    openDoneWeek = () => {
        const today = new Date();
        const start = new Date(today);
        const day = start.getDay();
        const diff = start.getDate() - day + (day === 0 ? -6 : 1);
        start.setDate(diff);
        start.setHours(0, 0, 0, 0);
        const end = new Date();
        end.setDate(end.getDate() + 1);
        end.setHours(0, 0, 0, 0);
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'done'],
            ['date_done', '>=', start.toISOString()],
            ['date_done', '<', end.toISOString()],
        ];
        this._openDelivered(domain, "Delivered — Week");
    };
    openDoneMonth = () => {
        const today = new Date();
        const start = new Date(today);
        start.setDate(today.getDate() - 29);
        start.setHours(0, 0, 0, 0);
        const end = new Date(today);
        end.setDate(end.getDate() + 1);
        end.setHours(0, 0, 0, 0);
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'done'],
            ['date_done', '>=', start.toISOString()],
            ['date_done', '<', end.toISOString()],
        ];
        this._openDelivered(domain, "Delivered — Month");
    };
    openStatusDelivered = () => {
        const domain = [
            ['state', '=', 'done'],
        ];
        this._openDelivered(domain, "Delivered Receipts");
    };
    openStatusInTransit = () => {
        const domain = [
            ['state', '=', 'assigned'],
            ['is_received', '=', false],
        ];
        this._openDelivered(domain, "In Transit Receipts");
    };
    openStatusDelivered = () => {
        const domain = [
            ['state', '=', 'done'],
        ];
        this._openDelivered(domain, "Delivered Receipts");
    };

    openStatusDelayed = () => {
        const now = new Date();

        const domain = [
            ['state', '=', 'assigned'],
            ['is_received', '=', true],
            ['scheduled_date', '<', now.toISOString()],
        ];

        this._openDelivered(domain, "Delayed Receipts");
    };


    openPartialDelivered = async () => {
        const res = await this.orm.call(
            "logistic.screen.data",
            "get_partial_delivered_lr",
            [],
            {}
        );
        const lrNumbers = (res && res.lr_numbers) || [];
        if (!lrNumbers.length) {
            this.notification.add("No Partial Delivered records found.", { type: "warning" });
            return;
        }
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'assigned'],
            ['lr_number', 'in', lrNumbers],
        ];
        this._openDelivered(domain, "Partial Delivered LRs");
    };
    async openPendingGRCDivision(divisionName) {
        const ids = await this.orm.call(
            "logistic.screen.data",
            "get_pickings_by_product_parent_pending",
            [divisionName]
        );
        const safeIds = Array.isArray(ids) ? ids : [];
        if (!safeIds.length) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Pending Receipts - ${divisionName}`,
            res_model: "stock.picking",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", safeIds]],
        });
    }
}

LogisticDashboard.template = "logistic_screen.logisticDashboard";
registry.category("actions").add("logistic_screen_tag", LogisticDashboard);