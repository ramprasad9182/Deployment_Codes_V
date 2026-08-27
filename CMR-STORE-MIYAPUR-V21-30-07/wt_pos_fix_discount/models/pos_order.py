# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	discount_fix = fields.Float(string='Discount (Fix)', default=0.0)
	discount_percentage = fields.Float(string='R.Discount(%)', readonly=True, digits=0, default=0.0)
	fix_discount_amount = fields.Float(string='MA.Discount')
	fix_discount_percentage = fields.Float(string='MA. Discount(%)')


class PosOrder(models.Model):
	_inherit = 'pos.order'

	def _get_invoice_lines_values(self, line_values, pos_line):
		inv_line_vals = super()._get_invoice_lines_values(line_values, pos_line)

		inv_line_vals.update({
			'discount_percentage': pos_line.discount_percentage,
			'discount_fix': pos_line.discount_fix,
		})

		return inv_line_vals


class PosOrderLine(models.Model):
	_inherit = 'pos.order.line'

	discount_fix = fields.Float(string='Discount (Fix)', digits=0, default=0.0)
	discount_percentage = fields.Float(string='Discount (%)', readonly=True, digits=0, compute="_compute_discount_display")
	is_fix_discount_line = fields.Boolean(string='Is Fix Discounted Line')
	fix_discount_amount = fields.Float(string='MA.Discount', compute="_compute_fix_discount", store=True,
	                                   help="This is only for Report Purpose, dont use in POS calculation")
	fix_discount_percentage = fields.Float(string='MA. Discount(%)', compute="_compute_fix_discount",
	                                       store=True, help="Report purpose only")

	def _export_for_ui(self, orderline):
		res = super(PosOrderLine, self)._export_for_ui(orderline)
		res['fix_discount'] = orderline.discount_fix
		res['is_fix_discount_line'] = orderline.is_fix_discount_line
		return res

	def _order_line_fields(self, line, session_id=None):
		res = super(PosOrderLine, self)._order_line_fields(line, session_id)
		if line[2] and 'fix_discount' in line[2]:
			res[2]['discount_fix'] = line[2]['fix_discount']
		if line[2] and 'is_fix_discount_line' in line[2]:
			res[2]['is_fix_discount_line'] = line[2]['is_fix_discount_line']
		return res

	@api.depends('discount_fix','discount')
	def _compute_discount_display(self):
		for line in self:
			if line.discount_fix:
				line.discount_percentage = 0.0
			else:
				line.discount_percentage = line.discount

	@api.depends('order_id.lines', 'order_id.lines.is_fix_discount_line', 'order_id.lines.price_subtotal_incl')
	def _compute_fix_discount(self):
		orders = self.mapped('order_id')
		discount_pct_per_order = {}
		eligible_lines_per_order = {}

		for order in orders:
			if not order:
				continue
			fix_discount_lines = order.lines.filtered(lambda l: l.is_fix_discount_line)
			if not fix_discount_lines:
				discount_pct_per_order[order.id] = 0.0
				eligible_lines_per_order[order.id] = self.env['pos.order.line']
				continue

			total_fix_discount = abs(sum(l.price_subtotal_incl for l in fix_discount_lines))
			eligible_lines = order.lines.filtered(
				lambda l: not l.is_fix_discount_line and not (
						getattr(l, 'is_reward_line', False) or
						getattr(l, 'reward_id', False) or
						getattr(l, 'discount_reward', False) or
						getattr(l, 'nhcl_reward_id', False)
				)
			)
			eligible_lines_per_order[order.id] = eligible_lines
			total_eligible_value = sum(l.price_subtotal_incl for l in eligible_lines)
			if total_eligible_value:
				discount_pct_per_order[order.id] = (total_fix_discount / total_eligible_value) * 100.0
			else:
				discount_pct_per_order[order.id] = 0.0

		for line in self:
			order = line.order_id
			if not order or order.id not in discount_pct_per_order:
				line.fix_discount_amount = 0.0
				line.fix_discount_percentage = 0.0
				continue

			eligible_lines = eligible_lines_per_order.get(order.id, self.env['pos.order.line'])
			if line in eligible_lines:
				pct = discount_pct_per_order[order.id]
				line.fix_discount_percentage = pct
				line.fix_discount_amount = line.price_subtotal_incl * (pct / 100.0)
			else:
				line.fix_discount_amount = 0.0
				line.fix_discount_percentage = 0.0
