# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request
from datetime import datetime


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _authenticate(cls, endpoint):
        res = super(IrHttp, cls)._authenticate(endpoint=endpoint)
        activity = request.env['recent.activity'].sudo().search(
            [('ks_session_id', '=', request.session.sid)])
        if not activity:
            request.env['recent.activity'].sudo().create({
                'ks_user_id': request.session.uid, 'ks_login_date': datetime.now(), 'ks_duration': 'Logged in',
                'ks_status': 'active',
                'ks_session_id': request.session.sid
            })
        if request.env['recent.activity'].sudo().search(
            [('ks_session_id', '=', request.session.sid), ('ks_status', '=', 'close')]):
            request.session.logout(keep_db=True)
        return res
