# models/pos_order.py
from odoo import models, fields, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    partner_phone = fields.Char(string="Phone", related='partner_id.phone', readonly=True)
    partner_phone_display = fields.Char(string="Customer Phone", compute='_compute_partner_phone_display', store=False)

    @api.depends('partner_id.phone')
    def _compute_partner_phone_display(self):
        for order in self:
            if order.partner_id:
                order.partner_phone_display = order.partner_id.phone
            else:
                order.partner_phone_display = ''