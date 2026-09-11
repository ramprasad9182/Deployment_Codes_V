# -*- coding: utf-8 -*-
from odoo import models, api, fields,_
from dateutil.relativedelta import relativedelta
from datetime import datetime, time, timedelta
from collections import Counter, defaultdict
import re
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_delayed = fields.Boolean(compute="_compute_is_delayed", store=True)

    @api.depends('received_datetime', 'scheduled_date')
    def _compute_is_delayed(self):
        for rec in self:
            rec.is_delayed = (
                rec.received_datetime
                and rec.scheduled_date
                and rec.received_datetime > rec.scheduled_date
            )

class LogisticScreenData(models.Model):
    _inherit = 'logistic.screen.data'


    @api.model
    def get_delivery_period_counts(self, **kwargs):
        Picking = self.env['stock.picking'].sudo()

        base_domain = [
            ('stock_picking_type', '=', 'receipt'),
            ('state', '=', 'done'),
        ]

        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=6)
        month_start = today - timedelta(days=29)

        def to_start(dt):
            return fields.Datetime.to_string(datetime.combine(dt, time.min))

        def to_end(dt):
            return fields.Datetime.to_string(datetime.combine(dt, time.max))

        # TODAY
        done_today = Picking.search_count(base_domain + [
            ('date_done', '>=', to_start(today)),
            ('date_done', '<=', to_end(today)),
        ])

        # WEEK
        done_week = Picking.search_count(base_domain + [
            ('date_done', '>=', to_start(week_start)),
            ('date_done', '<=', to_end(today)),
        ])

        # MONTH
        done_month = Picking.search_count(base_domain + [
            ('date_done', '>=', to_start(month_start)),
            ('date_done', '<=', to_end(today)),
        ])

        return {
            "done": {
                "today": done_today,
                "week": done_week,
                "month": done_month,
            }
        }

    @api.model
    def get_partial_delivered_lr(self, **kwargs):
        domain = [
            ('stock_picking_type', '=', 'receipt'),
            ('state', '=', 'assigned'),
            ('lr_number', '!=', False),
        ]

        if kwargs.get('date_from'):
            domain.append(('create_date', '>=', kwargs['date_from']))

        if kwargs.get('date_to'):
            domain.append(('create_date', '<=', kwargs['date_to']))

        groups = self.env['stock.picking'].read_group(
            domain,
            ['lr_number'],
            ['lr_number']
        )


        partial_lr_numbers = [
            g['lr_number']
            for g in groups
            if g.get('lr_number_count', 0) > 1
        ]

        return {
            "count": len(partial_lr_numbers),
            "lr_numbers": partial_lr_numbers,
        }

    @api.model
    def get_upcoming_counts(self, **kwargs):
        Picking = self.env['stock.picking'].sudo()

        base_domain = [
            ('stock_picking_type', '=', 'receipt'),
            ('state', '=', 'assigned'),
            ('is_received', '=', False),
        ]

        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=6)
        month_start = today - timedelta(days=29)

        def to_dt(d):
            return datetime.combine(d, time.min)

        today_start = to_dt(today)
        week_start_dt = to_dt(week_start)
        month_start_dt = to_dt(month_start)

        records = Picking.search(base_domain)

        today_count = 0
        week_count = 0
        month_count = 0

        for rec in records:
            if not rec.create_date:
                continue

            cd = rec.create_date

            if cd >= month_start_dt:
                month_count += 1

            if cd >= week_start_dt:
                week_count += 1

            if cd >= today_start:
                today_count += 1

        return {
            "draft": {
                "today": today_count,
                "week": week_count,
                "month": month_count,
            }
        }

    @api.model
    def get_delivery_status_counts(self):
        Picking = self.env['stock.picking']

        base_domain = [
            ('stock_picking_type', '=', 'receipt'),
        ]

        delivered = Picking.search_count(base_domain + [
            ('state', '=', 'done')
        ])

        in_transit = Picking.search_count(base_domain + [
            ('state', '=', 'assigned'),
            ('is_received', '=', False)
        ])

        pickings = Picking.search(base_domain + [
            ('state', '=', 'assigned'),
            ('is_received', '=', True),
        ])

        delayed = len(pickings.filtered(
            lambda p: p.received_datetime
                      and p.scheduled_date
                      and p.received_datetime > p.scheduled_date
        ))
        return {
            "status":
            {
                'delivered': delivered,
                'in_transit': in_transit,
                'delayed': delayed,
            }
        }

    @api.model
    def get_unopened_division_counts(self, top_n=10, **kwargs):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('state', '=', 'assigned'),
            ('picking_id.is_received', '=', True),
            ('picking_id.is_opened', '=', False),
        ]

        moves = Move.search_read(domain, ['product_id', 'picking_id'])

        if not moves:
            return {"total": 0, "items": []}

        category_map = defaultdict(set)

        for m in moves:
            product = m.get('product_id')
            picking = m.get('picking_id')

            if not product or not picking:
                continue

            name = product[1] or ''

            # remove [CODE]
            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            after = re.sub(r'\s+', ' ', after)

            parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else "Uncategorized"

            picking_id = picking[0]

            category_map[parent].add(picking_id)

        # build result
        results = []
        total = 0

        for name, picking_set in category_map.items():
            count = len(picking_set)
            total += count

            results.append({
                "division_name": name,
                "count": count,
            })

        results.sort(key=lambda x: x['count'], reverse=True)

        if top_n:
            results = results[:int(top_n)]

        return {
            "total": total,
            "items": results
        }

    @api.model
    def get_pickings_by_division(self, division_name):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('state', '=', 'assigned'),
            ('picking_id.is_received', '=', True),
            ('picking_id.is_opened', '=', False),
        ]

        moves = Move.search_read(domain, ['product_id', 'picking_id'])

        result_picking_ids = set()

        for m in moves:
            product = m.get('product_id')
            picking = m.get('picking_id')

            if not product or not picking:
                continue

            name = product[1] or ''

            # same parsing logic
            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            parts = [p.strip() for p in after.split('-') if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else "Uncategorized"

            if parent == division_name:
                result_picking_ids.add(picking[0])

        return list(result_picking_ids)

    @api.model
    def get_bales_against_lr(self, **kwargs):

        Picking = self.env['stock.picking'].sudo()

        domain = [
            ('stock_picking_type', '=', 'receipt'),
        ]

        pickings = Picking.search_read(domain, ['lr_number', 'state'])

        if not pickings:
            return {"open": 0, "unopen": 0}

        lr_map = {}

        for p in pickings:
            lr = p.get('lr_number') or 'NO_LR'
            state = p.get('state')

            if lr not in lr_map:
                lr_map[lr] = {
                    "assigned": False,
                    "done": False,
                }

            if state == 'assigned':
                lr_map[lr]["assigned"] = True

            if state == 'done':
                lr_map[lr]["done"] = True

        open_count = 0
        unopen_count = 0

        for lr, states in lr_map.items():

            if states["assigned"]:
                unopen_count += 1

            if states["done"]:
                open_count += 1

        return {
            "open": open_count,
            "unopen": unopen_count,
        }

    @api.model
    def get_pickings_by_lr_state(self, state_type):

        Picking = self.env['stock.picking'].sudo()

        domain = [
            ('stock_picking_type', '=', 'receipt'),
        ]

        pickings = Picking.search_read(domain, ['lr_number', 'state'])

        lr_map = {}

        for p in pickings:
            lr = p.get('lr_number') or 'NO_LR'
            state = p.get('state')
            pid = p.get('id')

            if lr not in lr_map:
                lr_map[lr] = {
                    "assigned": False,
                    "done": False,
                    "sample_id": pid,  # ✅ ONLY ONE ID
                }

            if state == 'assigned':
                lr_map[lr]["assigned"] = True

            if state == 'done':
                lr_map[lr]["done"] = True

        result_ids = []

        for lr, data in lr_map.items():

            if state_type == 'open' and data["done"]:
                result_ids.append(data["sample_id"])

            elif state_type == 'unopen' and data["assigned"]:
                result_ids.append(data["sample_id"])

        return result_ids


    @api.model
    def get_top_delivered_products(self, top_n=5, **kwargs):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.stock_picking_type', '=', 'receipt'),
            ('state', '=', 'done'),
        ]

        moves = Move.search_read(domain, ['product_id', 'picking_id'])

        if not moves:
            return {"total": 0, "max": 0, "items": []}

        # 1: parent → unique LR

        parent_map = defaultdict(set)

        for m in moves:
            product = m.get('product_id')
            picking = m.get('picking_id')

            if not product or not picking:
                continue

            name = product[1] or ''

            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            after = re.sub(r'\s+', ' ', after)
            parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else _("Uncategorized")

            parent_map[parent].add(picking[0])


        # 2: convert to list

        results = []
        for parent, picking_set in parent_map.items():
            results.append({
                "key": parent,
                "product_name": parent,
                "parent_category": parent,
                "count": len(picking_set),  # LR count
            })

        # 3: sort + top N
        results.sort(key=lambda x: x['count'], reverse=True)
        top = results[:int(top_n)]

        # 4: totals
        total = sum(item['count'] for item in top)
        max_count = max((item['count'] for item in top), default=0)

        return {
            "total": total,
            "max": max_count,
            "items": top
        }


    @api.model
    def get_pickings_by_product_parent(self, parent_name):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.stock_picking_type', '=', 'receipt'),
            ('state', '=', 'done'),
        ]

        moves = Move.search_read(domain, ['product_id', 'picking_id'])

        result_ids = set()

        import re

        for m in moves:
            product = m.get('product_id')
            picking = m.get('picking_id')

            if not product or not picking:
                continue

            name = product[1] or ''

            # same parsing logic
            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            after = re.sub(r'\s+', ' ', after)
            parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else "Uncategorized"

            if parent == parent_name:
                result_ids.add(picking[0])

        return list(result_ids)

    @api.model
    def get_pending_grc_division_bales(self, top_n=10, **kwargs):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.stock_picking_type', '=', 'receipt'),
            ('state', '=', 'assigned'),
            ('picking_id.is_received', '=', True),
            ('picking_id.is_opened', '=', False),
        ]

        moves = Move.search_read(domain, ['product_id', 'product_uom_qty', 'quantity'])

        if not moves:
            return {"items": []}

        from collections import defaultdict
        import re

        parent_qty = defaultdict(float)

        for m in moves:
            product = m.get('product_id')
            if not product:
                continue

            qty = m.get('product_uom_qty') or m.get('quantity') or 0

            name = product[1] or ''

            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            after = re.sub(r'\s+', ' ', after)
            parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else "Uncategorized"

            parent_qty[parent] += qty

        results = [
            {
                "division_name": parent,
                "parcel_bale_total": int(total_qty),
            }
            for parent, total_qty in parent_qty.items()
        ]

        results.sort(key=lambda x: x['parcel_bale_total'], reverse=True)

        return {
            "items": results[:int(top_n)]
        }

    @api.model
    def get_pickings_by_product_parent_pending(self, parent_name):

        Move = self.env['stock.move'].sudo()

        domain = [
            ('picking_id.stock_picking_type', '=', 'receipt'),
            ('state', '=', 'assigned'),
            ('picking_id.is_received', '=', True),
            ('picking_id.is_opened', '=', False),
        ]

        moves = Move.search_read(domain, ['product_id', 'picking_id'])

        result_ids = set()

        import re

        for m in moves:
            product = m.get('product_id')
            picking = m.get('picking_id')

            if not product or not picking:
                continue

            name = product[1] or ''

            rb = name.find(']')
            after = name[rb + 1:].strip() if rb != -1 else name.strip()

            parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

            if parts and len(parts[0]) == 1 and parts[0].isalpha():
                parent = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]
            else:
                parent = parts[0] if parts else "Uncategorized"

            if parent == parent_name:
                result_ids.add(picking[0])

        return list(result_ids)

