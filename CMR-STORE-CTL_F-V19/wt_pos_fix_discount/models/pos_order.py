# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	discount_fix = fields.Float(string='Discount (Fix)', default=0.0)
	discount_percentage = fields.Float(string='R.Discount(%)', readonly=True, digits=0, default=0.0)


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