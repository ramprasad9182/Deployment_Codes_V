from odoo import api,fields,models

class AccountMove(models.Model):
    _inherit = "account.move"

    eway_bill_ids = fields.One2many("eway.bill.details", "move_id", string="E-Way Bills")
    eway_bill_count = fields.Integer(string="E-Way Bill Count", compute="_compute_eway_bill_count")

    def _compute_eway_bill_count(self):
        for move in self:
            move.eway_bill_count = len(move.eway_bill_ids)

    def action_view_eway_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "tree,form",
            "domain": [("move_id", "=", self.id)],
            "context": {"default_move_id": self.id},
        }

    def action_create_eway_bill(self):
        for move in self:
            existing_eway = self.env["eway.bill.details"].search([("move_id", "=", move.id)], limit=1)
            if existing_eway:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "eway.bill.details",
                    "view_mode": "form",
                    "res_id": existing_eway.id,
                    "target": "current",
                }

            eway = self.env["eway.bill.details"].create({
                "name": move.name,
                "move_id": move.id,
                "vendor_id": move.partner_id.id,
                "item_ids": [
                    (0, 0, {
                        "product_id": ml.product_id.id,
                        "product_qty": ml.quantity,
                        "price_unit": ml.price_unit,
                    })
                    for ml in move.invoice_line_ids
                ],
            })

            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": eway.id,
                "target": "current",
            }
