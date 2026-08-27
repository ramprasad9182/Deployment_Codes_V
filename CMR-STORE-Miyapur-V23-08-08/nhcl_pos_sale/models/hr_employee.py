import re

from odoo import fields, models, api,_
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    """Add field into hr employee"""
    _inherit = 'hr.employee'

    limited_discount = fields.Integer(string="Discount Limit", help="Provide discount limit to each " "employee")
    allow_global_discount = fields.Boolean(string="POS - Global Discount Access")
    max_global_discount = fields.Float(string="Max Global Discount(%)")
    allow_amount_discount = fields.Boolean(string="POS - Amount Discount Access")
    max_amount_discount = fields.Float(string="Max Amount Discount")
    allow_selected_lines_discount = fields.Boolean(string="POS - Selected Lines Discount Access")
    max_selected_lines_discount = fields.Float(string="Max Selected Lines Discount(%)")
    store_manager = fields.Boolean(string="Store Manager")

    @api.constrains('max_global_discount', 'max_selected_lines_discount')
    def check_max_global_discount(self):
        for employee in self:
            if employee.max_global_discount > 100:
                raise ValidationError(_("You can't set Global Discount more then 100"))
            if employee.max_selected_lines_discount > 100:
                raise ValidationError(_("You can't set Selected Lines Discount more then 100"))


class InheritPosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_hr_employee(self):
        result = super()._loader_params_hr_employee()
        result['search_params']['fields'].append('allow_global_discount')
        result['search_params']['fields'].append('allow_amount_discount')
        result['search_params']['fields'].append('allow_selected_lines_discount')
        result['search_params']['fields'].append('max_global_discount')
        result['search_params']['fields'].append('max_amount_discount')
        result['search_params']['fields'].append('max_selected_lines_discount')
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'


    @api.constrains('phone', 'mobile')
    def _check_phone_mobile_length(self):
        for rec in self:
            for field in ['phone', 'mobile']:
                number = rec[field]

                if number:
                    digits = re.sub(r'\D', '', number)  # keep digits only

                    if len(digits) != 10:
                        raise ValidationError(_(
                            "Phone No must contain exactly 10 digits."
                        ))