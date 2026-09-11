from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class HoStoreMaster(models.Model):
    """Created nhcl.ho.store.master class to add fields and functions"""
    _name = "nhcl.ho.store.master"
    _description = "HO/Store Master"

    nhcl_store_id = fields.Char("Store ID", readonly=True, copy=False)
    nhcl_store_name = fields.Char(string='Store Name')
    nhcl_store_type = fields.Selection([('ho', 'HO'), ('store', 'Stores')], default='', string='Master Type')
    nhcl_location_id = fields.Char(string='Location')
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    nhcl_active = fields.Boolean(default=False, string="Status")
    nhcl_web_url = fields.Char('URL')
    nhcl_login_user = fields.Char('User')
    nhcl_password = fields.Char('Password')
    nhcl_effective_date = fields.Date('Effective Date')
    nhcl_create_date = fields.Date('Create Date', default=fields.Date.context_today)
    # nhcl_sink = fields.Boolean(default=False, string="Sink")



    def _compute_display_name(self):
        super()._compute_display_name()
        for i in self:
            i.display_name = f"{i.nhcl_store_name}"

    def activate_store(self):
        if self.nhcl_active == False:
            self.nhcl_active = True
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }

    def deactivate_store(self):
        if self.nhcl_active == True:
            self.nhcl_active = False
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }

