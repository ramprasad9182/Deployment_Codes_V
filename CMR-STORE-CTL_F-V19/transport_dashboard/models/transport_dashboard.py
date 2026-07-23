# models/stock_picking.py
from odoo import api, fields, models
from datetime import timedelta
import re
import logging
_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def get_transfer_dashboard_summary(self, **kwargs):
        Category = self.env['product.category']
        Move = self.env['stock.move']

        from datetime import timedelta
        from odoo import fields

        def _to_ids(val):
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        # ------------ inputs ------------
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period_days = kwargs.get("period_days")
        filter_cat_ids = _to_ids(kwargs.get("category_ids"))

        # ------------ ✅ UPDATED DOMAIN ------------
        domain = [
            ('picking_id.state', 'in', ['done', 'assigned']),
            '|',
            ('picking_id.stock_picking_type', '=', 'damage'),
            ('picking_id.picking_type_code', '=', 'outgoing'),
        ]

        # ------------ DATE FILTER ------------
        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt = fields.Datetime.to_datetime(end_date)
            domain += [
                ('picking_id.date_done', '>=', start_dt),
                ('picking_id.date_done', '<=', end_dt)
            ]
        elif period_days:
            today = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain.append(('picking_id.date_done', '>=', start_dt))

        # ------------ CATEGORY FILTER ------------
        if filter_cat_ids:
            domain.append(('product_id.categ_id', 'child_of', list(filter_cat_ids)))

        # ------------ GROUPING ------------
        groups = Move.read_group(
            domain,
            fields=['id:count'],
            groupby=['picking_id', 'product_id'],
            lazy=False,
        )

        if not groups:
            return {
                "total_deliveries": 0,
                "total_categories": 0,
                "rows": []
            }

        # ------------ PICKING FLAGS ------------
        picking_ids = {g['picking_id'][0] for g in groups if g.get('picking_id')}
        flags = {
            r['id']: (bool(r.get('is_received')), bool(r.get('is_opened')))
            for r in self.search_read(
                [('id', 'in', list(picking_ids))],
                ['id', 'is_received', 'is_opened']
            )
        }

        # ------------ PRODUCT → CATEGORY ------------
        prod_ids = {g['product_id'][0] for g in groups if g.get('product_id')}
        prod_rows = self.env['product.product'].search_read(
            [('id', 'in', list(prod_ids))],
            ['id', 'categ_id']
        )

        prod_leaf = {
            r['id']: (r['categ_id'][0] if r.get('categ_id') else False)
            for r in prod_rows
        }

        leaf_ids = {cid for cid in prod_leaf.values() if cid}

        # ------------ ROOT CATEGORY ------------
        root_of_leaf = {}
        root_name = {}

        if leaf_ids:
            for leaf in Category.browse(list(leaf_ids)):
                cur = leaf
                while cur.parent_id:
                    cur = cur.parent_id
                root_of_leaf[leaf.id] = cur.id
                if cur.id not in root_name:
                    root_name[cur.id] = cur.name or "Uncategorized"

        # ------------ AGGREGATION ------------
        seen_pairs = set()
        by_name = {}

        for g in groups:
            p = g.get('picking_id')
            prod = g.get('product_id')

            if not p or not prod:
                continue

            pid = p[0]
            prod_id = prod[0]

            leaf = prod_leaf.get(prod_id)
            if not leaf:
                continue

            root_id = root_of_leaf.get(leaf)
            if not root_id:
                continue

            pair = (pid, root_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            name = root_name.get(root_id, "Uncategorized")
            is_recv, is_open = flags.get(pid, (False, False))

            key = (name or "").strip().lower()

            agg = by_name.setdefault(key, {
                "name": name,
                "total": 0,
                "received": 0,
                "opened": 0
            })

            agg["total"] += 1

            if is_recv:
                agg["received"] += 1
                if is_open:
                    agg["opened"] += 1

        # ------------ FINAL ROWS ------------
        rows = []
        for _, d in by_name.items():
            total = d["total"]
            received = min(d["received"], total)
            opened = min(d["opened"], received)

            rows.append({
                "group_key": f"cat:{d['name']}",
                "category_name": d["name"],
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())

        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }

    @api.model
    def get_return_dashboard_summary(self, payload=None, **kwargs):
        kwargs = payload or kwargs or {}

        Category = self.env['product.category']
        Move = self.env['stock.move']
        Product = self.env['product.product']

        from datetime import timedelta
        from odoo import fields

        def _to_ids(val):
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        # ------------ inputs ------------
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period_days = kwargs.get("period_days")
        filter_cat_ids = _to_ids(kwargs.get("category_ids"))

        # ------------ ✅ FIXED DOMAIN ------------
        domain = [
            ('picking_id.state', 'in', ['done', 'assigned']),
            ('picking_id.picking_type_code', '=', 'incoming'),
        ]

        # ------------ DATE FILTER ------------
        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt = fields.Datetime.to_datetime(end_date)
            domain += [
                ('picking_id.date_done', '>=', start_dt),
                ('picking_id.date_done', '<=', end_dt)
            ]
        elif period_days:
            today = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain.append(('picking_id.date_done', '>=', start_dt))

        # ------------ CATEGORY FILTER ------------
        if filter_cat_ids:
            domain.append(('product_id.categ_id', 'child_of', list(filter_cat_ids)))

        # ------------ GROUPING ------------
        groups = Move.read_group(
            domain,
            fields=['id:count'],
            groupby=['picking_id', 'product_id'],
            lazy=False,
        )

        if not groups:
            return {
                "total_deliveries": 0,
                "total_categories": 0,
                "rows": []
            }

        # ------------ PICKING FLAGS ------------
        picking_ids = {g['picking_id'][0] for g in groups if g.get('picking_id')}
        flags = {
            r['id']: (bool(r.get('is_received')), bool(r.get('is_opened')))
            for r in self.search_read(
                [('id', 'in', list(picking_ids))],
                ['id', 'is_received', 'is_opened']
            )
        }

        # ------------ PRODUCT → CATEGORY ------------
        prod_ids = {g['product_id'][0] for g in groups if g.get('product_id')}
        prod_rows = Product.search_read(
            [('id', 'in', list(prod_ids))],
            ['id', 'categ_id']
        )

        prod_leaf = {
            r['id']: (r['categ_id'][0] if r.get('categ_id') else False)
            for r in prod_rows
        }

        leaf_ids = {cid for cid in prod_leaf.values() if cid}

        # ------------ ROOT CATEGORY ------------
        root_of_leaf = {}
        root_name = {}

        if leaf_ids:
            for leaf in Category.browse(list(leaf_ids)):
                cur = leaf
                while cur.parent_id:
                    cur = cur.parent_id
                root_of_leaf[leaf.id] = cur.id
                if cur.id not in root_name:
                    root_name[cur.id] = cur.name or "Uncategorized"

        # ------------ AGGREGATION ------------
        seen_pairs = set()
        per_root = {}

        for g in groups:
            p = g.get('picking_id')
            prod = g.get('product_id')

            if not p or not prod:
                continue

            pid = p[0]
            prod_id = prod[0]

            leaf_id = prod_leaf.get(prod_id)
            if not leaf_id:
                continue

            root_id = root_of_leaf.get(leaf_id)
            if not root_id:
                continue

            key = (pid, root_id)
            if key in seen_pairs:
                continue

            seen_pairs.add(key)

            name = root_name.get(root_id, "Uncategorized")
            is_recv, is_open = flags.get(pid, (False, False))

            rec = per_root.setdefault(root_id, {
                "name": name,
                "total": 0,
                "received": 0,
                "opened": 0
            })

            rec["total"] += 1

            if is_recv:
                rec["received"] += 1
                if is_open:
                    rec["opened"] += 1

        # ------------ FINAL ROWS ------------
        rows = []
        for rid, d in per_root.items():
            total = int(d["total"])
            received = min(int(d["received"]), total)
            opened = min(int(d["opened"]), received)

            rows.append({
                "group_key": f"root:{rid}",
                "category_name": d["name"],
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())

        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }



class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def get_parent_product(self):
        rows = self.search_read([('parent_id', '=', False)], ['id', 'name'], order='name asc')
        return {
            'parent_product': rows,  # [{id,name}]
            'parent_list': []  # empty = no preselected filter
        }

    @api.model
    def search_top_categories(self, q="", limit=50):
        domain = [("parent_id", "=", False)]
        if q:
            domain.append(("name", "ilike", q))
        recs = self.search(domain, limit=limit, order="name asc")
        return [{"id": r.id, "name": r.name} for r in recs]
