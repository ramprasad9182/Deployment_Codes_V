# -*- coding: utf-8 -*-
from odoo import fields, models


class MessageWizard(models.TransientModel):
    _name = "message.wizard"
    _description = 'Message'

    def get_default(self):
        if self.env.context.get("message", False):
            return self.env.context.get("message")
        return False

    name = fields.Text(string="Message", readonly=True, default=get_default)
