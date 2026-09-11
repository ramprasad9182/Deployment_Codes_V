# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api, _

class routes_details(models.Model):
    _name = 'dev.routes.details'
    _inherit = ['mail.thread']
    _description = 'Routes Details'
    _order = 'id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name')
    transpoter_id = fields.Many2one('dev.transport.details',string='Transporter',tracking=2)
    location_details_ids = fields.One2many('routes.location.details','routes_detail_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)


class routes_location_details(models.Model):
    _name = 'routes.location.details'
    _description = "routes location details"
    
    routes_detail_id = fields.Many2one('dev.routes.details',string='Routes Detail')
    
    source_location_id = fields.Many2one('dev.location.location',string='Source Location')
    destination_location_id = fields.Many2one('dev.location.location',string='Destination Location')
    distance = fields.Float(string='Distance(KM)')
    transport_charges = fields.Float(string='Transport Charges')
    time_hour = fields.Char(string='Time Hours')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    
    
    
    
        


    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
