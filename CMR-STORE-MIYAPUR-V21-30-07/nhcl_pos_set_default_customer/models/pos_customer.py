from odoo import fields, models


class PosContactMaster(models.Model):
    _name = 'pos.contact'

    name = fields.Char(string="Customer Name")
    phone_no = fields.Char(string="Phone Number")
    email = fields.Char(string="E mail")