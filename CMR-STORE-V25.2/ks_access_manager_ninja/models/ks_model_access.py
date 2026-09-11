# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools, http, exceptions
from odoo.api import call_kw
from odoo.http import request
from odoo.models import check_method_name


class KsDatasetInherit(http.Controller):

    @http.route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='json', auth="user")
    def call_kw(self, model, method, args, kwargs, path=None):
        # If system is readonly then restrict rpc calls
        if method in ['create', 'write', 'unlink'] and request.env['user.management'].sudo().search(
                [('ks_readonly', '=', True),
                 ('ks_user_ids', '=', request.context.get('uid')),
                 ('active', '=', True)]):
            return None

        profile_management = request.env['model.access'].sudo().search(
            [('ks_model_id.model', '=', model),
             ('ks_user_management_id.ks_user_ids', '=', request.context.get('uid')),
             ('ks_user_management_id.active', '=', True)], limit=1)

        if method == 'create' and profile_management.ks_hide_create:
            return None
        elif method == 'write' and profile_management.ks_hide_edit:
            return None
        elif method == 'unlink' and profile_management.ks_hide_delete:
            return None
        return self._call_kw(model, method, args, kwargs)

    def _call_kw(self, model, method, args, kwargs):
        check_method_name(method)
        return call_kw(request.env[model], method, args, kwargs)


class KsRemoveAction(models.Model):
    _name = 'model.access'
    _description = 'Remove Action from model'

    ks_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', ks_profile_domain_model)]")
    ks_server_action_ids = fields.Many2many('report.action.data', 'server_action_data_rel_ah',
                                            'action_action_id', 'server_action_id', 'Hide Actions',
                                            domain="[('ks_action_id.binding_model_id','=',ks_model_id),('ks_action_id.type','!=','ir.actions.report')]")
    ks_report_action_ids = fields.Many2many('report.action.data', 'remove_action_report_action_data_rel_ah',
                                            'action_action_id', 'report_action_id', 'Hide Reports',
                                            domain="[('ks_action_id.binding_model_id','=',ks_model_id),('ks_action_id.type','=','ir.actions.report')]")

    ks_model_readonly = fields.Boolean('Read-only')
    ks_hide_create = fields.Boolean(string='Hide Create')
    ks_hide_edit = fields.Boolean(string='Hide Edit')
    ks_hide_delete = fields.Boolean(string='Hide Delete')
    ks_hide_archive_unarchive = fields.Boolean(string='Hide Archive/Unarchive')
    ks_hide_duplicate = fields.Boolean(string='Hide Duplicate')
    ks_hide_export = fields.Boolean(string='Hide Export')
    ks_user_management_id = fields.Many2one('user.management', string='Management Id')
    ks_profile_domain_model = fields.Many2many('ir.model', related='ks_user_management_id.ks_profile_domain_model')


class KsRemoveActionData(models.Model):
    _name = 'report.action.data'
    _description = "Store Action Button Data"

    name = fields.Char(string='Name')
    ks_action_id = fields.Many2one('ir.actions.actions', string='Action')
