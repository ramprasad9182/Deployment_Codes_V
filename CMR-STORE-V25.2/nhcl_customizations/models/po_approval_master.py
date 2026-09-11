from odoo import fields,models,api,_
from odoo.exceptions import ValidationError


class ApprovalsMaster(models.Model):
    _name = 'po.approvals.master'
    _description = "po approvals master"

    date = fields.Date("Date")
    min_approvals = fields.Integer("Min Approvals")
    approval_type = fields.Char("Type")
    max_approvals = fields.Integer("Max Approvals")
    approval_limit = fields.Integer("Level Of Approvals")
    approval_active = fields.Boolean(string='Active', default=True)
    table_type = fields.Char("Table Type")
    nhcl_approval_state = fields.Selection(
        [('draft', 'Draft'), ('activate', 'Active'), ('in_activate', 'Deactivate')],
        string='Status', default='draft')
