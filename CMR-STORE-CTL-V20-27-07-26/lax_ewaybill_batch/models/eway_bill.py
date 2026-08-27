from odoo import fields, models

class EwayBillDetails(models.Model):
    _inherit = "eway.bill.details"

    batch_id = fields.Many2one("stock.picking.batch", string="Stock Picking Batch")
