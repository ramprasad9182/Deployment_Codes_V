# -*- coding: utf-8 -*-
import subprocess

import httpagentparser
import paramiko

from odoo import http, models,fields,_,api
import logging
from odoo.http import request

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)  # Set up Odoo's logger

class PosConfigInherit(models.Model):
    _inherit = 'pos.config'

    system_ip_address = fields.Char("System Device Name",required=True)
    user_name = fields.Char(string="User Name")
    password = fields.Char(string="Password")

    @api.constrains('payment_method_ids')
    def _check_payment_method_ids_journal(self):
        # override to disable original constraint
        pass

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        current_ip = http.request.httprequest.remote_addr if http.request and http.request.httprequest else ''
        print("===>current", current_ip)

        request = http.request.httprequest

        real_ip = (
                request.headers.get('X-Forwarded-For')
                or request.headers.get('X-Real-IP')
                or request.remote_addr
        )

        print("REAL IP:", real_ip)


        if not self.env.user.has_group('point_of_sale.group_pos_manager'):
            # Apply domain filter if the user is not a POS manager
            domain = [('system_ip_address', '=', real_ip)]
        else:
            # No domain filter for POS managers
            domain = []

        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order,
                                       count_limit=count_limit)



    def get_device_name_via_ssh(self, host, port, username, password):
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(host, port=port, username=username, password=password)

            # Run the command to get the device's hostname
            stdin, stdout, stderr = ssh_client.exec_command('hostname')
            device_name = stdout.read().decode().strip()

            ssh_client.close()
            return device_name
        except Exception as e:
            _logger.error(f"Error connecting via SSH: {e}")
            return None

    def open_ui(self):
        remote_ip = http.request.httprequest.remote_addr

        _logger.warning("Current IP: %s", remote_ip)
        _logger.warning("Configured IP: %s", self.system_ip_address)

        if remote_ip != self.system_ip_address:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'This terminal is not authorized',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        return super().open_ui()
