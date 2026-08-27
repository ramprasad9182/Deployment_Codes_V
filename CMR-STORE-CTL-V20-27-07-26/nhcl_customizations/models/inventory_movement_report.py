from odoo import models, fields
from datetime import datetime, time


class InventoryMovementReport(models.Model):
    _name = "inventory.movement.report"
    _description = "Inventory Movement Report"
    _rec_name = "product_id"

    product_id = fields.Many2one('product.product', string="Product")

    # receipt_qty = fields.Float(string="Receipt Qty", readonly=True)
    # delivery_qty = fields.Float(string="Delivery Qty", readonly=True)
    #
    # maintodamage_qty = fields.Float(string="Main2Damage", readonly=True)
    # goodsreturn_damage_qty = fields.Float(string="Goods Return Damage", readonly=True)
    # damagetomain_qty = fields.Float(string="Damage2Main", readonly=True)
    #
    # pos_order_qty = fields.Float(string="POS Order", readonly=True)
    # pos_exchange_qty = fields.Float(string="POS Exchange", readonly=True)
    # pos_return_qty = fields.Float(string="POS Return", readonly=True)

    receipt_qty = fields.Float(string="Receipt Qty", readonly=True)
    receipt_rs_total = fields.Float(string="Receipt Value", readonly=True)

    delivery_qty = fields.Float(string="Delivery Qty", readonly=True)
    delivery_rs_total = fields.Float(string="Delivery Value", readonly=True)

    maintodamage_qty = fields.Float(string="Main2Damage Qty", readonly=True)
    maintodamage_rs_total = fields.Float(string="Main2Damage Value", readonly=True)

    goodsreturn_damage_qty = fields.Float(string="Goods Return Damage Qty", readonly=True)
    goodsreturn_damage_rs_total = fields.Float(string="Goods Return Damage Value", readonly=True)

    damagetomain_qty = fields.Float(string="Damage2Main Qty", readonly=True)
    damagetomain_rs_total = fields.Float(string="Damage2Main Value", readonly=True)

    pos_order_qty = fields.Float(string="POS Order Qty", readonly=True)
    pos_order_rs_total = fields.Float(string="POS Order Value", readonly=True)

    pos_exchange_qty = fields.Float(string="POS Exchange Qty", readonly=True)
    pos_exchange_rs_total = fields.Float(string="POS Exchange Value", readonly=True)

    pos_return_qty = fields.Float(string="Return TO Main Qty", readonly=True)
    pos_return_rs_total = fields.Float(string="Return TO Main Value", readonly=True)

    division_name = fields.Char(string="Division")
    section_name = fields.Char(string="Section")
    department_name = fields.Char(string="Department")
    category_name = fields.Char(string="Category")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")

    opening_qty = fields.Float(string="Opening Qty", readonly=True)
    opening_rs_total = fields.Float(string="Opening Value", readonly=True)
    closing_qty = fields.Float(string="Closing Qty", readonly=True)
    closing_rs_total = fields.Float(string="Closing Value", readonly=True)



    def action_view_moves(self):
        self.ensure_one()

        domain = [
            ('state', '=', 'done'),
            ('move_ids.product_id', '=', self.product_id.id),
        ]

        if self.from_date:
            domain.append(('date_done', '>=', datetime.combine(self.from_date, time.min)))

        if self.to_date:
            domain.append(('date_done', '<=',  datetime.combine(self.to_date, time.max)))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Pickings',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'create': False}
        }

    def action_open_date_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Date Range',
            'res_model': 'inventory.movement.report.wizard',
            'view_mode': 'form',
            'target': 'new',
        }