from odoo import api,fields,models,_


class EwayBillDetails(models.Model):
    _name = "ewaybill.error.code"
    _description = "E-way Bill Error Code"

    code = fields.Char(string="Error Code")
    name = fields.Char(string="Error Description")