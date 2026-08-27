from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    eway_bill_ids = fields.Many2many(
        "eway.bill.details",
        "eway_bill_picking_rel",
        "picking_id",
        "eway_bill_id",
        string="E-Way Bills",
    )
    eway_bill_count = fields.Integer(string="E-Way Bill Count", compute="_compute_eway_bill_count")

    def _compute_eway_bill_count(self):
        for picking in self:
            picking.eway_bill_count = len(picking.eway_bill_ids)

    def action_view_eway_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.eway_bill_ids.ids)],
            "context": {"default_picking_ids": [(4, self.id)]},
        }

    def action_create_eway_bill(self):
        for picking in self:
            if picking.picking_type_code != 'outgoing':
                raise UserError(_("E-Way Bill can only be created for Outgoing/Delivery transfers!"))
            existing_eway = picking.eway_bill_ids[:1]
            if existing_eway:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "eway.bill.details",
                    "view_mode": "form",
                    "res_id": existing_eway.id,
                    "target": "current",
                }

            products_qty = {}
            for ml in picking.move_ids_without_package:
                qty = ml.quantity if picking.state == 'done' and ml.quantity else ml.product_uom_qty
                if qty <= 0:
                    continue
                products_qty[ml.product_id] = products_qty.get(ml.product_id, 0.0) + qty

            item_lines = []
            for product, qty in products_qty.items():
                item_lines.append((0, 0, {
                    "product_id": product.id,
                    "product_qty": qty,
                    "price_unit": product.lst_price or 0.0,
                }))

            if not item_lines:
                raise UserError(_("No items found to create E-Way Bill."))

            eway = self.env["eway.bill.details"].create({
                "name": picking.name,
                "picking_id": picking.id,
                "picking_ids": [(6, 0, picking.ids)],
                "vendor_id": picking.partner_id.id,
                "item_ids": item_lines,
            })

            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": eway.id,
                "target": "current",
            }


