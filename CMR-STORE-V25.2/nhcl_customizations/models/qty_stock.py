import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    @api.model
    def get_receipt_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'receipt'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_receipt_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'receipt'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_main_damage_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'main_damage'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_main_damage_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'main_damage'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_damage_main_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'damage_main'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_damage_main_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'damage_main'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_return_main_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'return_main'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_return_main_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'return_main'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_delivery_orders_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'return'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_delivery_orders_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'return'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_good_return_damage_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'damage'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_good_return_damage_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'damage'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_pos_order_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'pos_order'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_pos_order_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'pos_order'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_manufacturing_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'manufacturing'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_manufacturing_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'manufacturing'),
            ('state', '=', 'assigned')
        ])


    @api.model
    def get_pos_exchange_done_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'exchange'),
            ('state', '=', 'done')
        ])
    @api.model
    def get_pos_exchange_assigned_count(self):
        return self.env['stock.picking'].search_count([
            ('stock_picking_type', '=', 'exchange'),
            ('state', '=', 'assigned')
        ])

    @api.model
    def get_dashboard_counts(self):
        # if you already have individual methods, call them here to keep logic centralized
        return {
            'receipts': {
                'done': self.get_receipt_done_count(),
                'assigned': self.get_receipt_assigned_count(),
            },
            'main_damage_JC': {
                'done': self.get_main_damage_done_count(),
                'assigned': self.get_main_damage_assigned_count(),
            },
            'damage_main_JC': {
                'done': self.get_damage_main_done_count(),
                'assigned': self.get_damage_main_assigned_count(),
            },
            'return_main_JC': {
                'done': self.get_return_main_done_count(),
                'assigned': self.get_return_main_assigned_count(),
            },
            'delivery_orders': {
                'done': self.get_delivery_orders_done_count(),
                'assigned': self.get_delivery_orders_assigned_count(),
            },
            'good_return_damage': {
                'done': self.get_good_return_damage_done_count(),
                'assigned': self.get_good_return_damage_assigned_count(),
            },
            'pos_orders': {
                'done': self.get_pos_order_done_count(),
                'assigned': self.get_pos_order_assigned_count(),
            },
            'manufacturing': {
                'done': self.get_manufacturing_done_count(),
                'assigned': self.get_manufacturing_assigned_count(),
            },
            'pos_exchange': {
                'done': self.get_pos_exchange_done_count(),
                'assigned': self.get_pos_exchange_assigned_count(),
            },
        }


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _format_number(self, value):
        """Return nicely formatted string: thousands sep, no .0 for integers, 2 decimals otherwise."""
        try:
            v = float(value or 0.0)
        except Exception:
            return "0"
        if abs(v - int(v)) < 1e-9:
            return "{:,.0f}".format(v)  # no decimals for whole numbers
        return "{:,.2f}".format(v)      # two decimals otherwise

    @api.model
    def get_receipts_totals(self, **kwargs):

        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()

        domain_base = [('picking_type_id.stock_picking_type', '=', 'receipt')]

        # compute done_total (state = done)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_main_damage_totals(self, **kwargs):

        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()


        domain_base = [('picking_type_id.stock_picking_type', '=', 'main_damage')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result


    @api.model
    def get_damage_main_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()

        domain_base = [('picking_type_id.stock_picking_type', '=', 'damage_main')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_return_main_totals(self, **kwargs):

        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()

        domain_base = [('picking_type_id.stock_picking_type', '=', 'return_main')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_delivery_orders_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()
        domain_base = [('picking_type_id.stock_picking_type', '=', 'return')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_good_return_damage_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()
        domain_base = [('picking_type_id.stock_picking_type', '=', 'damage')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_PoS_Orders_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()
        domain_base = [('picking_type_id.stock_picking_type', '=', 'pos_order')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_manufacturing_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()
        domain_base = [('picking_type_id.stock_picking_type', '=', 'manufacturing')]

        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result

    @api.model
    def get_pos_exchange_totals(self, **kwargs):
        result = {'done': 0.0, 'ready': 0.0, 'done_display': '0', 'ready_display': '0'}
        Move = self.env['stock.move'].sudo()


        domain_base = [('picking_type_id.stock_picking_type', '=', 'exchange')]


        # compute done_total (state = done)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'done')], ['quantity:sum'], [])
            done_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'done')])
            done_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        # compute ready_total (state = assigned)
        try:
            g = Move.read_group(domain_base + [('state', '=', 'assigned')], ['quantity:sum'], [])
            ready_total = float(g[0].get('quantity') or 0.0) if g else 0.0
        except Exception:
            moves = Move.search(domain_base + [('state', '=', 'assigned')])
            ready_total = sum(float(getattr(m, 'quantity', 0.0) or 0.0) for m in moves)

        result['done'] = float(done_total)
        result['ready'] = float(ready_total)
        result['done_display'] = self._format_number(result['done'])
        result['ready_display'] = self._format_number(result['ready'])

        return result
