# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Laxicon Solution (<http://www.laxicon.in>).
#
#    For Module Support : info@laxicon.in
#
##############################################################################
from odoo import api, fields, models, _


class Portcode(models.Model):
    _name = "port.code"
    _description = "Port code"
    _rec_name = 'port_code'

    port_code = fields.Char(string="Port Code")
    port_name = fields.Char(string="Port Name")