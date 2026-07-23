from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    sale_receipt = fields.Boolean(string='Enable POS Receipt sequence')
    sale_receipt_sequence_id = fields.Many2one('ir.sequence', string="Set POS sequence")
