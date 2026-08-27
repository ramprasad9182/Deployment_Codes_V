from odoo import models, fields, api


class Picking(models.Model):
    _inherit = "stock.picking"

    is_opened = fields.Boolean(string="Is Opened", help="Tick if the bale/package is opened.")
    is_received = fields.Boolean(string="Is Received", help="Tick if the bale/package is received.")
    received_datetime = fields.Datetime(string="Received On", readonly=True)

    def write(self, vals):
        if 'is_received' in vals and vals.get('is_received'):
            vals['received_datetime'] = fields.Datetime.now()

        return super().write(vals)


    def button_validate(self):
        res = super().button_validate()
        for rec in self:
            if rec.state == 'done':
                rec.is_opened = True
                rec.is_received = True
        return res


