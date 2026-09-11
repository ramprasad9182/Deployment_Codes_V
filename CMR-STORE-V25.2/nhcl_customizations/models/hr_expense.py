from odoo import api, fields, Command, models, _


class HrExpense(models.Model):
    _inherit = "hr.expense"

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sale_employee = fields.Selection([('yes','YES'), ('no','NO')], string="Sale Employee")

class HrJob(models.Model):
    _inherit = 'hr.job'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
