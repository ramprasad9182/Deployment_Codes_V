from odoo import models
from odoo.http import request
import socket
import logging

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _get_client_ip(self):
        try:
            if request:
                _logger.info("REMOTE_ADDR = %s", request.httprequest.remote_addr)
                _logger.info("HEADERS = %s", dict(request.httprequest.headers))
                headers = request.httprequest.headers

                ip = (
                        headers.get('X-Real-IP')
                        or request.httprequest.remote_addr
                )

                if ip and ',' in ip:
                    ip = ip.split(',')[0].strip()

                return ip
        except Exception:
            pass

        return False

    def _get_server_ip(self):
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return False

    def _create_module_audit(self, action):
        client_ip = self._get_client_ip()
        server_ip = self._get_server_ip()

        hostname = False
        try:
            hostname = socket.gethostname()
        except Exception:
            pass

        for module in self:
            self.env['module.audit.log'].sudo().create({
                'module_name': module.name,
                'action': action,
                'user_id': self.env.user.id,
                'user_login': self.env.user.login,
                'client_ip': client_ip,
                'server_ip': server_ip,
                'hostname': hostname,
                'database_name': self.env.cr.dbname,
                'module_state': module.state,
            })

            _logger.warning(
                "MODULE AUDIT | User=%s | Action=%s | Module=%s | Client IP=%s",
                self.env.user.login,
                action,
                module.name,
                client_ip
            )

    def button_immediate_install(self):
        self._create_module_audit('install')
        return super().button_immediate_install()

    def button_immediate_upgrade(self):
        self._create_module_audit('upgrade')
        return super().button_immediate_upgrade()

    def button_immediate_uninstall(self):
        self._create_module_audit('uninstall')
        return super().button_immediate_uninstall()