# -*- coding: utf-8 -*-
from odoo import fields, models, api, _, service,tools
from odoo.exceptions import UserError
from odoo.http import request


class KsFieldAccess(models.Model):
    _name = 'field.access'
    _inherit = ['mail.thread']
    _description = 'Field Access'

    ks_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', ks_profile_domain_model )]")
    ks_field_id = fields.Many2many('ir.model.fields',
                                   string='Field')
    ks_field_invisible = fields.Boolean(string='Invisible')
    ks_field_readonly = fields.Boolean(string='Readonly')
    ks_field_required = fields.Boolean(string='Required')
    ks_field_external_link = fields.Boolean(string='Remove External Link')
    ks_user_management_id = fields.Many2one('user.management', string='Management')
    ks_profile_domain_model = fields.Many2many('ir.model', related='ks_user_management_id.ks_profile_domain_model')

    ks_tracking = fields.Boolean(string="Tracking")

    @api.constrains('ks_field_required', 'ks_field_readonly')

    def ks_check_field_access(self):
        profile = self.env['user.management']
        for rec in self:
            if rec.ks_field_required and rec.ks_field_readonly:
                raise UserError(_('You can not set field as Readonly and Required at same time.'))
            elif rec.ks_field_required and rec.ks_field_invisible:
                raise UserError(_('You can not set field as Invisible and Required at same time.'))
            for field in rec.ks_field_id:
                if rec.ks_field_required:
                    if self.search([('ks_field_invisible','=',True),('ks_field_id','in',field.id),('ks_user_management_id.ks_user_ids','in',self.ks_user_management_id.ks_user_ids.ids)]):
                        raise UserError(_('You can not set field as Invisible and Required at same time.'))
                    elif self.search([('ks_field_readonly','=',True),('ks_field_id','in',field.id),('ks_user_management_id.ks_user_ids','in',self.ks_user_management_id.ks_user_ids.ids)]):
                        raise UserError(_('You can not set field as Readonly and Required at same time.'))
                elif rec.ks_field_invisible:
                    if self.search([('ks_field_required','=',True),('ks_field_id','in',field.id),('ks_user_management_id.ks_user_ids','in',self.ks_user_management_id.ks_user_ids.ids)]):
                        raise UserError(_('You can not set field as Invisible and Required at same time.'))
                elif rec.ks_field_readonly:
                    if self.search([('ks_field_required','=',True),('ks_field_id','in',field.id),('ks_user_management_id.ks_user_ids','in',self.ks_user_management_id.ks_user_ids.ids)]):
                        raise UserError(_('You can not set field as Readonly and Required at same time.'))



    @api.constrains('ks_field_id','ks_tracking')
    def action_restart(self):
        self.env.registry.clear_cache()

    def get_track_fields(self):
        model_fields = []
        if self.ks_tracking == True:
            for field_id in self.ks_field_id:
                model_fields.append(field_id.name)
        return model_fields


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @tools.ormcache('self.env.uid', 'self.env.su')
    def _track_get_fields(self):
        model_fields = {
            name
            for name, field in self._fields.items()
            if getattr(field, 'tracking', None) or getattr(field, 'track_visibility', None)
        }
        for value in self:
            extra_fields = value.get_track_fields()
            for i in extra_fields:
                model_fields.add(i)
        return model_fields and set(self.fields_get(model_fields, attributes=()))

    def get_track_fields(self):
        model_fields = []
        hidden_fields = None
        company_lst = self.env.context.get('allowed_company_ids', [])
        if company_lst:
            hidden_fields = self.env['field.access'].sudo().search(
                [('ks_model_id.model', '=', self._name),
                 ('ks_user_management_id.active', '=', True),
                 ('ks_user_management_id.ks_user_ids', 'in', self._uid),
                 ('ks_user_management_id.ks_company_ids', 'in', company_lst)
                 ])
        else:
            hidden_fields = self.env['field.access'].sudo().search(
                [('ks_model_id.model', '=', self._name),
                 ('ks_user_management_id.active', '=', True),
                 ('ks_user_management_id.ks_user_ids', 'in', self._uid),
                 ])

        hidden_field = self.env['global.tracking'].sudo().search(
            [('g_model_id.model', '=', self._name),
             ])
        for h in hidden_fields:
            if h['ks_tracking'] == True:
                for hide_field in hidden_fields:
                    for field_id in hide_field.ks_field_id:
                        model_fields.append(field_id.name)
        for hide_field in hidden_field:
            for field_id in hide_field.g_field_id:
                model_fields.append(field_id.name)
        return model_fields

