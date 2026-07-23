from odoo import fields, models, _


class AccountTax(models.Model):
    _inherit = 'account.tax'

    max_amount = fields.Float(string='Maximum Amount', digits=0, required=True,
                              help="")
    min_amount = fields.Float(string='Minimum Amount', digits=0, required=True,
                              help="")
