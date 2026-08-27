from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_sale_receipt = fields.Boolean(related='pos_config_id.sale_receipt', readonly=False, string='POS Custom receipt sequence')
    pos_sale_receipt_sequence_id = fields.Many2one(related='pos_config_id.sale_receipt_sequence_id', readonly=False, string='Set POS sequence')
