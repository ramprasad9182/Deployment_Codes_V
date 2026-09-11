/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

function _parseNumber(v) {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const cleaned = String(v).replace(/[^\d.\-]/g, "");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}
function _fmt(n) {
  return (Math.abs(n - Math.round(n)) < 1e-9)
    ? new Intl.NumberFormat().format(Math.round(n))
    : new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}


export class StockOwlDashboard extends Component {
    static template = "StockOwlDashboard";

    setup() {

        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.actionService = useService("action");

        this.state = useState({
          receipts:   { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0" },
          main_damage_JC:  { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          damage_main_JC:   { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          return_main_JC:   { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          delivery_orders:   { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0" },
          good_return_damage:   { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          pos_orders:  { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          manufacturing:  { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
          pos_exchange:  { done: 0, ready: 0, done_display: "0", ready_display: "0", done_rec: "0", ready_rec: "0"  },
        });
        onWillStart(async () => {
            await Promise.all([
                this.fetchReceiptsTotals(),
                this.fetchMainDamageJCTotals(),
                this.fetchDamageMainJCTotals(),
                this.fetchReturnJCTotals(),
                this.fetchDeliveryOrdersTotals(),
                this.fetchGoodsReturnDamageTotals(),
                this.fetchPosOrdersTotals(),
                this.fetchManufacturingTotals(),
                this.fetchPosExchangeTotals(),
                this.updateReceiptStates(),
            ]);
        });
    }

    async fetchReceiptsTotals() {
      try {
        // Call server method WITHOUT sending any domain (server uses literal domain)
        const res = await this.orm.call(
          "stock.picking.type",
          "get_receipts_totals",
          [],
          { kwargs: {} } // intentionally empty
        );

        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.receipts) {
          this.state.receipts = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        // Update object properties (do not overwrite the object)
        this.state.receipts.done = done;
        this.state.receipts.ready = ready;
        this.state.receipts.done_display  = _fmt(done);
        this.state.receipts.ready_display = _fmt(ready);

        console.log("[fetchReceiptsTotals] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[fetchReceiptsTotals] failed:", err);

        if (!this.state.receipts) {
          this.state.receipts = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        } else {
          // ensure properties exist and are reset
          this.state.receipts.done = 0;
          this.state.receipts.ready = 0;
          this.state.receipts.done_display = "0";
          this.state.receipts.ready_display = "0";
        }
      }
    }

     async fetchMainDamageJCTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_main_damage_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.main_damage_JC) {
          this.state.main_damage_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.main_damage_JC.done = done;
        this.state.main_damage_JC.ready = ready;
        this.state.main_damage_JC.done_display  = _fmt(done);
        this.state.main_damage_JC.ready_display = _fmt(ready);

        console.log("[fetchMainDamageJCTotals] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[fetchMainDamageJCTotals] failed:", err);

        if (!this.state.main_damage_JC) {
          this.state.main_damage_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.main_damage_JC.done = 0;
        this.state.main_damage_JC.ready = 0;
        this.state.main_damage_JC.done_display = "0";
        this.state.main_damage_JC.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load Main Damage (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchDamageMainJCTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_damage_main_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.damage_main_JC) {
          this.state.damage_main_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.damage_main_JC.done = done;
        this.state.damage_main_JC.ready = ready;
        this.state.damage_main_JC.done_display  = _fmt(done);
        this.state.damage_main_JC.ready_display = _fmt(ready);

        console.log("[fetchdamage_main_JCTotals] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[fetchdamage_main_JCTotals] failed:", err);

        if (!this.state.damage_main_JC) {
          this.state.damage_main_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.damage_main_JC.done = 0;
        this.state.damage_main_JC.ready = 0;
        this.state.damage_main_JC.done_display = "0";
        this.state.damage_main_JC.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load damage_main_JC (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchReturnJCTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_return_main_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.return_main_JC) {
          this.state.return_main_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.return_main_JC.done = done;
        this.state.return_main_JC.ready = ready;
        this.state.return_main_JC.done_display  = _fmt(done);
        this.state.return_main_JC.ready_display = _fmt(ready);

        console.log("[fetchreturn_main_JCTotals] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[fetchreturn_main_JCTotals] failed:", err);

        if (!this.state.return_main_JC) {
          this.state.return_main_JC = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.return_main_JC.done = 0;
        this.state.return_main_JC.ready = 0;
        this.state.return_main_JC.done_display = "0";
        this.state.return_main_JC.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load return_main_JC (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchDeliveryOrdersTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_delivery_orders_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.delivery_orders) {
          this.state.delivery_orders = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.delivery_orders.done = done;
        this.state.delivery_orders.ready = ready;
        this.state.delivery_orders.done_display  = _fmt(done);
        this.state.delivery_orders.ready_display = _fmt(ready);

        console.log("[fetchdelivery_ordersTotals] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[fetchdelivery_ordersTotals] failed:", err);

        if (!this.state.delivery_orders) {
          this.state.delivery_orders = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.delivery_orders.done = 0;
        this.state.delivery_orders.ready = 0;
        this.state.delivery_orders.done_display = "0";
        this.state.delivery_orders.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load delivery_orders (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchGoodsReturnDamageTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_good_return_damage_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.good_return_damage) {
          this.state.good_return_damage = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.good_return_damage.done = done;
        this.state.good_return_damage.ready = ready;
        this.state.good_return_damage.done_display  = _fmt(done);
        this.state.good_return_damage.ready_display = _fmt(ready);

        console.log("[good_return_damage] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[good_return_damage] failed:", err);

        if (!this.state.good_return_damage) {
          this.state.good_return_damage = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.good_return_damage.done = 0;
        this.state.good_return_damage.ready = 0;
        this.state.good_return_damage.done_display = "0";
        this.state.good_return_damage.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load good_return_damage (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchPosOrdersTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_PoS_Orders_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.pos_orders) {
          this.state.pos_orders = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.pos_orders.done = done;
        this.state.pos_orders.ready = ready;
        this.state.pos_orders.done_display  = _fmt(done);
        this.state.pos_orders.ready_display = _fmt(ready);

        console.log("[pos_orders] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[pos_orders] failed:", err);

        if (!this.state.pos_orders) {
          this.state.pos_orders = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.pos_orders.done = 0;
        this.state.pos_orders.ready = 0;
        this.state.pos_orders.done_display = "0";
        this.state.pos_orders.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load pos_orders (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

     async fetchManufacturingTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_manufacturing_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.manufacturing) {
          this.state.manufacturing = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.manufacturing.done = done;
        this.state.manufacturing.ready = ready;
        this.state.manufacturing.done_display  = _fmt(done);
        this.state.manufacturing.ready_display = _fmt(ready);

        console.log("[manufacturing] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[manufacturing] failed:", err);

        if (!this.state.manufacturing) {
          this.state.manufacturing = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.manufacturing.done = 0;
        this.state.manufacturing.ready = 0;
        this.state.manufacturing.done_display = "0";
        this.state.manufacturing.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load manufacturing (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

    async fetchPosExchangeTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "stock.picking.type",
          "get_pos_exchange_totals",
          [],
          { kwargs: filters }
        );
        const done  = _parseNumber(res?.done ?? res?.total ?? res?.qty ?? res) || 0;
        const ready = _parseNumber(res?.ready ?? res?.assigned ?? res?.product_uom_qty ?? 0) || 0;

        if (!this.state.pos_exchange) {
          this.state.pos_exchange = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }

        this.state.pos_exchange.done = done;
        this.state.pos_exchange.ready = ready;
        this.state.pos_exchange.done_display  = _fmt(done);
        this.state.pos_exchange.ready_display = _fmt(ready);

        console.log("[pos_exchange] done:", done, "ready:", ready);
        return { done, ready };
      } catch (err) {
        console.error("[pos_exchange] failed:", err);

        if (!this.state.pos_exchange) {
          this.state.pos_exchange = { done: 0, ready: 0, done_display: "0", ready_display: "0" };
        }
        this.state.pos_exchange.done = 0;
        this.state.pos_exchange.ready = 0;
        this.state.pos_exchange.done_display = "0";
        this.state.pos_exchange.ready_display = "0";

        if (this.notification && typeof this.notification.add === "function") {
          this.notification.add("Failed to load pos_exchange (JC) totals.", { type: "danger" });
        }
        return { done: 0, ready: 0 };
      }
    }

    async updateReceiptStates() {
        try {
            const counts = await this.orm.call(
                "stock.picking",
                "get_dashboard_counts",
                [],
                {}
            );

            // Batch update all states in one place (reduce repeated renders)
            this.state.receipts.done_rec = counts.receipts?.done ?? 0;
            this.state.receipts.ready_rec = counts.receipts?.assigned ?? 0;

            this.state.main_damage_JC.done_rec = counts.main_damage_JC?.done ?? 0;
            this.state.main_damage_JC.ready_rec = counts.main_damage_JC?.assigned ?? 0;

            this.state.damage_main_JC.done_rec = counts.damage_main_JC?.done ?? 0;
            this.state.damage_main_JC.ready_rec = counts.damage_main_JC?.assigned ?? 0;

            this.state.return_main_JC.done_rec = counts.return_main_JC?.done ?? 0;
            this.state.return_main_JC.ready_rec = counts.return_main_JC?.assigned ?? 0;

            this.state.delivery_orders.done_rec = counts.delivery_orders?.done ?? 0;
            this.state.delivery_orders.ready_rec = counts.delivery_orders?.assigned ?? 0;

            this.state.good_return_damage.done_rec = counts.good_return_damage?.done ?? 0;
            this.state.good_return_damage.ready_rec = counts.good_return_damage?.assigned ?? 0;

            this.state.pos_orders.done_rec = counts.pos_orders?.done ?? 0;
            this.state.pos_orders.ready_rec = counts.pos_orders?.assigned ?? 0;

            this.state.manufacturing.done_rec = counts.manufacturing?.done ?? 0;
            this.state.manufacturing.ready_rec = counts.manufacturing?.assigned ?? 0;

            this.state.pos_exchange.done_rec = counts.pos_exchange?.done ?? 0;
            this.state.pos_exchange.ready_rec = counts.pos_exchange?.assigned ?? 0;

            this.render?.();
        } catch (error) {
            console.error("Error updating receipt states:", error);
        }
    }

    open_receipts_done() {
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Receipts",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_receipts_ready() {
        const domain = [
            ['stock_picking_type', '=', 'receipt'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Receipts",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Main_Damage_done() {
        const domain = [
            ['stock_picking_type', '=', 'main_damage'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Main-Damage",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Main_Damage_ready() {
        const domain = [
            ['stock_picking_type', '=', 'main_damage'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Main-Damage",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Damage_Main_done() {
        const domain = [
            ['stock_picking_type', '=', 'damage_main'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Damage-Main",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Damage_Main_ready() {
        const domain = [
            ['stock_picking_type', '=', 'damage_main'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Damage-Main",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Return_Main_done() {
        const domain = [
            ['stock_picking_type', '=', 'return_main'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Return-Main",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Return_Main_ready() {
        const domain = [
            ['stock_picking_type', '=', 'return_main'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Return-Main",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Return_done() {
        const domain = [
            ['stock_picking_type', '=', 'return'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Return",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Return_ready() {
        const domain = [
            ['stock_picking_type', '=', 'return'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Return",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Damage_done() {
        const domain = [
            ['stock_picking_type', '=', 'damage'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Damage",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Damage_ready() {
        const domain = [
            ['stock_picking_type', '=', 'damage'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Damage",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_POS_Order_done() {
        const domain = [
            ['stock_picking_type', '=', 'pos_order'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed POS-Order",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_POS_Order_ready() {
        const domain = [
            ['stock_picking_type', '=', 'pos_order'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending POS-Order",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Manufacturing_done() {
        const domain = [
            ['stock_picking_type', '=', 'manufacturing'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed Manufacturing",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Manufacturing_ready() {
        const domain = [
            ['stock_picking_type', '=', 'manufacturing'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending Manufacturing",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Exchange_done() {
        const domain = [
            ['stock_picking_type', '=', 'exchange'],
            ['state', '=', 'done']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Completed POS-Exchange",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }
    open_Exchange_ready() {
        const domain = [
            ['stock_picking_type', '=', 'exchange'],
            ['state', '=', 'assigned']
        ];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'stock.picking',
            name: "Pending POS-Exchange",
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                create: false,
                edit: false,
            },
        });
    }

}

registry.category("actions").add("StockOwlDashboard", StockOwlDashboard);








