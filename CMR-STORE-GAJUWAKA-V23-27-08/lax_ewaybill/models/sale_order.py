from odoo import api,fields,models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    eway_bill_ids = fields.One2many("eway.bill.details", "order_id", string="E-Way Bills")
    eway_bill_count = fields.Integer(string="E-Way Bill Count", compute="_compute_eway_bill_count")

    def _compute_eway_bill_count(self):
        for order in self:
            order.eway_bill_count = len(order.eway_bill_ids)

    def action_view_eway_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "tree,form",
            "domain": [("order_id", "=", self.id)],
            "context": {"default_order_id": self.id},
        }

    def action_create_eway_bill(self):
        for order in self:
            existing_eway = self.env["eway.bill.details"].search([("order_id", "=", order.id)], limit=1)
            if existing_eway:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "eway.bill.details",
                    "view_mode": "form",
                    "res_id": existing_eway.id,
                    "target": "current",
                }

            eway = self.env["eway.bill.details"].create({
                "name": order.name,
                "order_id": order.id,
                "vendor_id": order.partner_id.id,
                "item_ids": [
                    (0, 0, {
                        "product_id": ml.product_id.id,
                        "product_qty": ml.product_uom_qty,
                        "price_unit": ml.price_unit,
                    })
                    for ml in order.order_line
                ],
            })

            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": eway.id,
                "target": "current",
            }
