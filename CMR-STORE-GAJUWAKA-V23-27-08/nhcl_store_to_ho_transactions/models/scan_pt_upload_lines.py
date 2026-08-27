from odoo import models, fields


class ScanPtUploadLines(models.Model):
    _name = 'scan.pt.upload.lines'
    _description = 'Scan PT Upload Lines'

    order_id = fields.Many2one(
        'purchase.order',
        string="Purchase Order",
        ondelete='cascade'
    )
    barcode = fields.Char(
        string="Barcode"
    )

    quantity = fields.Float(
        string="Quantity"
    )
