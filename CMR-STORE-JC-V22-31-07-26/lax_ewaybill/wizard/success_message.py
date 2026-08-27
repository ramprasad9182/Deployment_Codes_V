# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MessageWizardEwaybill(models.TransientModel):
    _name = "message.wizard.ewaybill"
    _description = 'Message'

    name = fields.Text(string="Message", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super(MessageWizardEwaybill, self).default_get(fields_list)
        if 'name' in fields_list:
            msg = self.env.context.get('message') or self.env.context.get('default_name')
            if msg:
                res['name'] = msg
        return res
