# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.http import request
from odoo.exceptions import UserError

class KsAccessManagement(models.Model):
    _name = 'user.management'
    _description = 'User Access Management'

    color = fields.Integer(string='Color Index')

    def ks_default_profile_ids(self):
        return self.env['user.profiles'].sudo().search([('implied_ids', '=', self.env.ref('base.group_system').id)]).ids

    name = fields.Char(string='Name')
    active = fields.Boolean(string='Active', default=True)
    ks_readonly = fields.Boolean(string="Readonly",
                                 help='Make the whole database readonly for the users added in this profile.')
    ks_hide_chatter = fields.Boolean(string="Hide Chatter", help="Hide all chatter's for the selected user")
    ks_disable_debug_mode = fields.Boolean(string='Disable Developer Mode',
                                           help="Deactivate debug mode for the selected users.")
    ks_user_ids = fields.Many2many('res.users', 'user_management_users_rel', 'user_management_id', 'user_id',
                                   'Users')
    ks_user_rel_ids = fields.Many2many('res.users', 'res_user_store_rel', string='Store user profiles',
                                       compute='ks_compute_profile_ids')
    ks_profile_ids = fields.Many2many('user.profiles', string='Profiles', required=True)
    ks_company_ids = fields.Many2many('res.company', string='Companies', required=True)
    ks_hide_menu_ids = fields.Many2many('ir.ui.menu', string='Menu')
    ks_model_access_line = fields.One2many('model.access', 'ks_user_management_id', string='Model Access')
    ks_hide_field_line = fields.One2many('field.access', 'ks_user_management_id', string='Field Access')
    ks_domain_access_line = fields.One2many('domain.access', 'ks_user_management_id', string='Domain Access')
    ks_button_tab_access_line = fields.One2many('button.tab.access', 'ks_user_management_id', string='Button Access')
    ks_users_count = fields.Integer(string='Users Count', compute='_compute_users_count')
    ks_hide_filters_groups_line = fields.One2many('filter.group.access', 'ks_user_management_id', string='Filter Group')
    ks_ir_model_access = fields.Many2many('ir.model.access', string='Access Rights', readonly=True)
    ks_ir_rule = fields.Many2many('ir.rule', string='Record Rules', readonly=True)
    ks_profile_domain_model = fields.Many2many('ir.model')
    ks_profile_based_menu = fields.Many2many('ir.ui.menu', 'related_menu_for_profiles', 'profile_ids', 'menu_ids',
                                             compute='_compute_profile_based_menu', store=True)
    is_profile = fields.Boolean(string='Profile Exist')

    @api.onchange('is_profile', 'ks_profile_ids')
    def onchange_is_profile(self):
        """ Onchange that the profile is selected inside profile management."""
        if self.ks_profile_ids:
            self.is_profile = True
        else:
            self.is_profile = False
        self.ks_user_ids = [(6, 0, self.ks_profile_ids.mapped('ks_user_ids').ids)]
        self.ks_user_rel_ids = [(6, 0, self.ks_profile_ids.mapped('ks_user_ids').ids)]
        access_rights = []
        record_rules = []
        model_ids = []
        for profile in self.ks_profile_ids:
            while True:
                access_rights += profile.mapped('implied_ids').model_access.ids
                record_rules += profile.mapped('implied_ids').rule_groups.ids
                model_ids.extend(profile.mapped('implied_ids').model_access.mapped('model_id').ids)
                if profile.implied_ids:
                    profile = profile.implied_ids
                else:
                    break
        record_rules += self.env['res.groups'].sudo().search([('custom', '=', True)]).mapped('rule_groups').ids
        self.ks_ir_model_access = [(6, 0, access_rights)]
        self.ks_ir_rule = [(6, 0, record_rules)]
        self.ks_profile_domain_model = [(6, 0, model_ids)]

    @api.constrains('name')
    def check_name(self):
        """Restrict admin to create rule as same name which is exist"""
        for rec in self:
            student = self.env['user.management'].sudo().search([('name', '=', rec.name), ('id', '!=', rec.id)])
            if student:
                raise UserError('Name must be unique for managements.')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(KsAccessManagement, self).create(vals_list)
        return res

    @api.depends('ks_users_count')
    def _compute_users_count(self):
        """Compute total user which is selected inside selected profiles"""
        for rec in self:
            rec.ks_users_count = len(self.ks_user_ids)

    @api.depends('ks_profile_based_menu', 'ks_profile_ids')
    def _compute_profile_based_menu(self):
        """Compute menu which is for the selected profile"""
        visible_menu_ids = []
        for rec in self.ks_profile_ids:
            last_group = rec.implied_ids
            while True:
                if last_group:
                    visible_menu_ids.extend(last_group.menu_access.ids)
                    last_group = last_group.implied_ids
                else:
                    break
        self.sudo().write({'ks_profile_based_menu': [(6, 0, list(set(visible_menu_ids)))]})

    @api.depends('ks_profile_ids', 'ks_profile_ids.ks_user_ids')
    def ks_compute_profile_ids(self):
        """Compute profiles users and access rights and domain for selected profile model"""
        for rec in self:
            rec.ks_user_ids = [(6, 0, rec.ks_profile_ids.mapped('ks_user_ids').ids)]
            rec.ks_user_rel_ids = [(6, 0, rec.ks_profile_ids.mapped('ks_user_ids').ids)]
            access_rights = []
            record_rules = []
            model_ids = []
            for profile in rec.ks_profile_ids:
                while True:
                    access_rights += profile.mapped('implied_ids').model_access.ids
                    record_rules += profile.mapped('implied_ids').rule_groups.ids
                    model_ids.extend(profile.mapped('implied_ids').model_access.mapped('model_id').ids)
                    if profile.implied_ids:
                        profile = profile.implied_ids
                    else:
                        break
            record_rules += self.env['res.groups'].sudo().search([('custom', '=', True)]).mapped('rule_groups').ids
            rec.ks_ir_model_access = [(6, 0, access_rights)]
            rec.ks_ir_rule = [(6, 0, record_rules)]
            self.ks_profile_domain_model = [(6, 0, model_ids)]

    def write(self, vals):
        res = super(KsAccessManagement, self).write(vals)
        # self.clear_caches()
        if vals.get('ks_user_ids'):
            for domain in self.ks_domain_access_line:
                users = self.env['res.users'].sudo().search(
                    [('ks_user_management_id', '=', self.id),
                     ('ks_user_management_id.active', '=', True)])
                domain.ks_rule_id.groups.users = [(6, 0, users.ids)]
        return res

    def unlink(self):
        for domain in self.ks_domain_access_line:
            domain.unlink()
        res = super(KsAccessManagement, self).unlink()
        return res

    def ks_activate_rule(self):
        """ Activate User Management Rule."""
        self.active = True
        users = self.env['res.users'].sudo().search(
            [('ks_user_management_id', '=', self.id), ('ks_user_management_id.active', '=', True)])
        for domain in self.ks_domain_access_line:
            domain.ks_rule_id.sudo().write({'active': True})

    def ks_deactivate_rule(self):
        """ Deactivate User Management Rule."""
        self.active = False
        users = self.env['res.users'].sudo().search(
            [('ks_user_management_id', '=', self.id), ('ks_user_management_id.active', '=', True)])
        for domain in self.ks_domain_access_line:
            domain.ks_rule_id.sudo().write({'active': False})

    def ks_view_profile_users(self):
        """Open users tree view"""
        return {
            'name': _('Profile Users'),
            'type': 'ir.actions.act_window',
            'view_type': 'list',
            'view_mode': 'list',
            'res_model': 'res.users',
            'view_id': self.env.ref('base.view_users_tree').id,
            'target': 'current',
            'domain': [('id', 'in', self.ks_user_ids.ids)],
            'context': {'create': False},

        }

    def ks_view_profile_record_rules(self):
        """ Open record rules tree view"""
        action = self.env["ir.actions.actions"]._for_xml_id("base.action_rule")
        action["domain"] = [("id", "in", self.ks_ir_rule.ids)]
        return action

    def ks_view_profile_access_rights(self):
        """" Open Access rights tree view"""
        action = self.env["ir.actions.actions"]._for_xml_id("base.ir_access_act")
        action["domain"] = [("id", "in", self.ks_ir_model_access.ids)]
        return action

    def ks_search_action_button(self, model):
        """Hide archive/unarchive and export buttons for selected user based on models."""
        hide_element = []
        lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
        is_archive_hide = self.env['model.access'].sudo().search(
            [('ks_model_id.model', '=', model), ('ks_user_management_id.active', '=', True),
             ('ks_user_management_id.ks_company_ids', 'in', lst),
             ('ks_user_management_id.ks_user_ids', 'in', self.env.user.id), ('ks_hide_archive_unarchive', '=', True)], limit=1)
        is_export_hide = self.env['model.access'].sudo().search(
            [('ks_model_id.model', '=', model), ('ks_user_management_id.active', '=', True),
             ('ks_user_management_id.ks_company_ids', 'in', lst),
             ('ks_user_management_id.ks_user_ids', 'in', self.env.user.id), ('ks_hide_export', '=', True)], limit=1)
        if is_archive_hide:
            hide_element = hide_element + ['archive', 'unarchive']
        if is_export_hide:
            hide_element = hide_element + ['export']
        return hide_element

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """ While duplicating profile management, the profile management name save as (copy)"""
        default = dict(default or {},
                       name=_("%s (copy)", self.name))
        return super().copy(default=default)


class ResCompany(models.Model):
    _inherit = 'res.company'

    color = fields.Integer(string='Color Index')
