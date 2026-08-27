from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter
from odoo.tools.misc import format_date


class MasterSequence(models.Model):
    """Created nhcl.master.sequence class to add fields and functions"""
    _name = 'nhcl.master.sequence'
    _description = "Sequence Master"

    nhcl_data = fields.Date(string='Date', default=fields.Date.today, copy=False)
    nhcl_prefix = fields.Char(string='Prefix', copy=False)
    nhcl_code = fields.Char(string='Code', copy=False)
    nhcl_type = fields.Char(string='Type', copy=False)
    nhcl_padding = fields.Integer(string='Padding', copy=False)
    nhcl_next_number = fields.Integer(string='Next Number', copy=False)
    nhcl_active = fields.Boolean(string='Active', default=True, copy=False)
    nhcl_state = fields.Selection([('draft', 'Draft'), ('activate', 'Activated'), ('in_activate', 'De Activated')],
                                  string='Status', default='draft', copy=False)

    def activate_sequence(self):
        if self.nhcl_next_number and self.nhcl_prefix and self.nhcl_code and self.nhcl_state in ['draft',
                                                                                                 'in_activate']:
            a = self.env['ir.sequence'].search([('code', '=', self.nhcl_code)])
            a.prefix = self.nhcl_prefix
            a.padding = self.nhcl_padding
            a.code = self.nhcl_code
            a.number_next_actual = self.nhcl_next_number
            self.nhcl_state = 'activate'

    def deactivate_sequence(self):
        if self.nhcl_state == 'activate':
            self.nhcl_state = 'in_activate'
            self.nhcl_active = False
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }

