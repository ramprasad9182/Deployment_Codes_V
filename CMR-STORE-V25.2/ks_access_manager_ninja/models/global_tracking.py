# -*- coding: utf-8 -*-
from odoo import fields, models, api, _, service,tools
from odoo.exceptions import UserError
from odoo.http import request


class KsGlobalTrackingFirst(models.Model):
    _name = 'global.tracking.first'
    _description = 'Global Tracking Fist'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name')
    global_tracking_line = fields.One2many('global.tracking', 'gt_first')

    @api.constrains('global_tracking_line')
    def action_restart(self):
        self.env.registry.clear_cache()
    #
    # @tools.ormcache('self.env.uid', 'self.env.su')
    # def _track_get_fields(self):
    #     res = super(KsGlobalTrackingFirst, self)._track_get_fields()
    #     extra = self.get_track_fields_global()
    #     for i in extra:
    #         res.update(i)
    #     return res
    #
    def get_track_fields(self):
        model_fields = []
        hidden_fields = self.env['global.tracking'].sudo().search(
            [('g_model_id.model', '=', self._name),
             ])
        for hide_field in self.global_tracking_line:
            for field_id in hide_field.g_field_id:
                model_fields.append(field_id.name)
        return model_fields

class KsGlobalTracking(models.Model):
    _name = 'global.tracking'
    _description = 'Global Tracking'
    _inherit = ['mail.thread']

    g_model_id = fields.Many2one('ir.model', string='Model')
    g_field_id = fields.Many2many('ir.model.fields', string='Field')
    global_tracking = fields.Boolean(string="Global Tracking")
    profile_tracking = fields.Boolean(string="Profile Tracking")
    profile_id = fields.Many2many('res.users')
    gt_first = fields.Many2one('global.tracking.first')

    # def get_track_fields(self):
    #     model_fields = []
    #     hidden_fields = self.env['global.tracking'].sudo().search(
    #         [('g_model_id.model', '=', self._name),
    #          ])
    #     for hide_field in self.global_tracking_line:
    #         for field_id in hide_field.g_field_id:
    #             model_fields.append(field_id.name)
    #     return model_fields


# class MailThread(models.AbstractModel):
#     _inherit = 'mail.thread'
#
#     @tools.ormcache('self.env.uid', 'self.env.su')
#     def _track_get_fields(self):
#         model_fields = {
#             name
#             for name, field in self._fields.items()
#             if getattr(field, 'tracking', None) or getattr(field, 'track_visibility', None)
#         }
#         for value in self:
#             extra_fields = value.get_track_fields_global()
#             for i in extra_fields:
#                 model_fields.add(i)
#         return model_fields and set(self.fields_get(model_fields, attributes=()))
#
#     def get_track_fields_global(self):
#         model_fields = []
#         hidden_fields = self.env['global.tracking'].sudo().search(
#             [('g_model_id.model', '=', self._name),
#              ])
#         for hide_field in hidden_fields:
#             for field_id in hide_field.g_field_id:
#                 model_fields.append(field_id.name)
#         return model_fields
