from odoo import models, fields

class LicenseKeyUserCreateWizard(models.TransientModel):
    _name = 'license.key.user.create.wizard'
    _description = 'Confirm User Creation from License Key'

    license_id = fields.Many2one('license.key', string="License", required=True)

    def action_create_users(self):
        # You can call your line creation logic here or trigger something else
        self.license_id._create_license_lines_from_decrypted_data()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

class LicenseKeyCreateUserWizard(models.TransientModel):
    _name = 'license.key.create.users.wizard'
    _description = 'Confirmed the User Creation from License Lines'

    users_license_id = fields.Many2one('license.key', string="License", required=True)

    def action_create_users_and_employees(self):
        # You can call your line creation logic here or trigger something else
        self.users_license_id.action_for_create_users()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancelled(self):
        return {'type': 'ir.actions.act_window_close'}
