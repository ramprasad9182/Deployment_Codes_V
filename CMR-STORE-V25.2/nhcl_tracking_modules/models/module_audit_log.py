from odoo import models, fields, api
from odoo.http import request
import socket


class ModuleAuditLog(models.Model):
    _name = 'module.audit.log'
    _description = 'Module Audit Log'
    _order = 'create_date desc'

    module_name = fields.Char(
        string='Module Name',
        required=True,
        readonly=True
    )

    action = fields.Selection([
        ('install', 'Install'),
        ('upgrade', 'Upgrade'),
        ('uninstall', 'Uninstall'),
    ], required=True, readonly=True)

    user_id = fields.Many2one(
        'res.users',
        string='User',
        readonly=True
    )

    user_login = fields.Char(
        string='User Login',
        readonly=True
    )

    client_ip = fields.Char(
        string='Client IP',
        readonly=True
    )

    server_ip = fields.Char(
        string='Server IP',
        readonly=True
    )

    hostname = fields.Char(
        string='Hostname',
        readonly=True
    )

    database_name = fields.Char(
        string='Database',
        readonly=True
    )

    module_state = fields.Char(
        string='Module State',
        readonly=True
    )

    notes = fields.Text(
        string='Notes',
        readonly=True
    )