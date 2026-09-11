from odoo import models, fields

class PosOrder(models.Model):
    _inherit = 'pos.order'

    user_allow_return_products = fields.Boolean(
        compute="_compute_user_allow_return_products"
    )

    def _compute_user_allow_return_products(self):
        for rec in self:
            rec.user_allow_return_products = rec.env.user.allow_return_products