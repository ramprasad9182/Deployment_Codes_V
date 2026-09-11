from odoo import api,fields,models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    eway_bill_ids = fields.One2many("eway.bill.details", "picking_id", string="E-Way Bills")
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
            "domain": [("picking_id", "=", self.id)],
            "context": {"default_picking_id": self.id},
        }

    def action_create_eway_bill(self):
        for picking in self:
            existing_eway = self.env["eway.bill.details"].search([("picking_id", "=", picking.id)], limit=1)
            if existing_eway:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "eway.bill.details",
                    "view_mode": "form",
                    "res_id": existing_eway.id,
                    "target": "current",
                }

            eway = self.env["eway.bill.details"].create({
                "name": picking.name,
                "picking_id": picking.id,
                "vendor_id": picking.partner_id.id,
                "item_ids": [
                    (0, 0, {
                        "product_id": ml.product_id.id,
                        "product_qty": ml.product_uom_qty,
                        "price_unit": ml.product_id.lst_price,
                    })
                    for ml in picking.move_ids_without_package
                ],
            })

            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": eway.id,
                "target": "current",
            }
