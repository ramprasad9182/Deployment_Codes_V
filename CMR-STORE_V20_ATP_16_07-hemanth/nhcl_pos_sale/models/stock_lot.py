from odoo import api, models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'

    product_qty_pos = fields.Float('On Hand Quantity POS', compute='_product_qty_pos', store=True)

    @api.depends('product_qty')
    def _product_qty_pos(self):
        for lot in self:
            lot.product_qty_pos = lot.product_qty


class StockPicking(models.Model):
    _inherit = "stock.picking"

    amount_discount = fields.Float(compute="compute_amount_discount", string="Line Discount", store=True)
    amount_reward_discount = fields.Float(compute="compute_amount_discount", string="R.Discount(A)", store=True)

    @api.depends('move_ids_without_package', 'move_ids_without_package.nhcl_gdiscount',
                 'move_ids_without_package.nhcl_discount', 'move_ids_without_package.nhcl_is_fix_discount_line',
                 'move_ids_without_package.total_discount', 'move_ids_without_package.total_reward_discount')
    def compute_amount_discount(self):
        for picking in self:
            picking.amount_reward_discount = sum(picking.move_ids_without_package.mapped('total_reward_discount'))
            picking.amount_discount = sum(picking.move_ids_without_package.mapped('total_discount'))
            lines = picking.move_ids_without_package.filtered(lambda line: line.nhcl_is_fix_discount_line)
            picking.amount_discount += -sum(lines.mapped('nhcl_rsp'))


class StockMove(models.Model):
    _inherit = "stock.move"

    total_discount = fields.Float(compute="_compute_total_discount", string="Line Discount", store=True)
    total_reward_discount = fields.Float(compute="_compute_total_discount", string="R.Discount(A)", store=True)

    @api.depends('nhcl_gdiscount', 'nhcl_discount', 'pos_order_lines')
    def _compute_total_discount(self):
        for line in self:
            # net_amount = line.price_unit * line.quantity
            # total_discount = (net_amount * (line.nhcl_gdiscount + line.nhcl_discount) / 100)
            # pos_line = line.pos_order_lines
            # if pos_line.nhcl_reward_id or pos_line.discount_reward or pos_line.is_reward_line or pos_line.reward_id:
            #     line.total_reward_discount = total_discount
            #     line.total_discount = 0.00
            # else:
            #     line.total_discount = total_discount
            #     line.total_reward_discount = 0.00
            pos_line = line.pos_order_lines
            line.total_reward_discount = pos_line.total_reward_discount
            line.total_discount = pos_line.total_discount
