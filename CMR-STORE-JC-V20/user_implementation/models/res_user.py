from odoo import models,fields,api, _
from datetime import date
from odoo.exceptions import AccessDenied
import logging
_logger = logging.getLogger(__name__)

class Users(models.Model):
    _inherit = 'res.users'

    expiry_date = fields.Date(string="License Expiry Date", store= True)
    user_license_id = fields.Many2one("license.key.line",string="User License Id")

    @api.model
    def cron_deactivate_expired_users(self):
        today = date.today()
        expired_users = self.search([
            ('expiry_date', '<', today),
            ('active', '=', True)
        ])
        for user in expired_users:
            user.active = False

    def _check_credentials(self, password, user_agent_env):
        res = super()._check_credentials(password, user_agent_env)
        for user in self:
            if user.expiry_date and user.expiry_date < fields.Date.today():
                _logger.warning(
                    "Login blocked: User %s expired on %s",
                    user.login,
                    user.expiry_date
                )
                raise AccessDenied(_("Your account has expired. Please contact the administrator."))

        return res


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    expiry_date = fields.Date(string="License Expiry Date")
    employee_license_id = fields.Many2one("license.key.line", string="User License Id")

    @api.model
    def cron_deactivate_expired_employee(self):
        today = date.today()
        expired_employees = self.search([
            ('expiry_date', '<', today),
            ('active', '=', True)
        ])
        for employee in expired_employees:
            employee.active = False