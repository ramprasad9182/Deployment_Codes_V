# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.http import request
from odoo.exceptions import ValidationError

class KsDomainAccess(models.Model):
    _name = 'domain.access'
    _description = 'Domain Access'

    ks_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', ks_profile_domain_model )]")
    ks_model_name = fields.Char(related='ks_model_id.model', string='Model Name')
    ks_create_access = fields.Boolean(string='Create')
    ks_read_access = fields.Boolean(string='Read', default=True)
    ks_write_access = fields.Boolean(string='Write')
    ks_delete_access = fields.Boolean(string='Delete')
    ks_apply_domain = fields.Boolean(string='Apply Domain')
    ks_domain = fields.Text(string="Domain", default='[]')
    ks_user_management_id = fields.Many2one('user.management', string='Management Rule')
    ks_rule_id = fields.Many2one('ir.rule', string='Rule')
    ks_profile_domain_model = fields.Many2many('ir.model', related='ks_user_management_id.ks_profile_domain_model')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(KsDomainAccess, self).create(vals_list)
        # Create record rule for the domain access.
        res.ks_create_domain_access()
        return res

    def write(self, vals):
        """Update record rule for the domain access."""
        res = super(KsDomainAccess, self).write(vals)
        for model in self:
            data = {
                'name': model.ks_model_id.name + ' Custom domain',
                'model_id': model.ks_model_id.id,
                'domain_force': model.ks_domain,
                'perm_create': model.ks_create_access,
                'perm_write': model.ks_write_access,
                'perm_read': model.ks_read_access,
                'perm_unlink': model.ks_delete_access,
            }
            model.ks_rule_id.sudo().write(data)
        return res

    @api.constrains('domain_force')
    def _check_domain(self):
        eval_context = self._eval_context()
        for rule in self:
            if rule.active and rule.domain_force:
                try:
                    domain = safe_eval(rule.domain_force, eval_context)
                    expression.expression(domain, self.env[rule.model_id.model].sudo())
                except Exception as e:
                    raise ValidationError(_('Invalid domain: %s', e))

    def unlink(self, rule=False):
        """Unlink record rule for the domain access."""
        for model in self:
            if not rule:
                model.ks_rule_id.sudo().unlink()
        res = super(KsDomainAccess, self).unlink()
        return res

    def ks_create_domain_access(self):
        for model in self:
            data = {
                'name': model.ks_model_id.name + model.ks_user_management_id.name,
                'model_id': model.ks_model_id.id,
                'domain_force': model.ks_domain,
                'perm_create': model.ks_create_access,
                'perm_write': model.ks_write_access,
                'perm_read': model.ks_read_access,
                'perm_unlink': model.ks_delete_access,
                # 'groups': model.ks_create_group(),
                'ks_domain_access_id': model.id,
                'custom': True

            }
            rule_id = self.env['ir.rule'].sudo().create(data)
            model.ks_rule_id = rule_id.id

    def ks_create_group(self):
        user_ids = self.ks_user_management_id.ks_user_ids
        group_values = {
            'name': self.ks_user_management_id.name + ' ' + self.ks_model_id.name,
            'users': user_ids,
            'custom': True,
            'comment': 'This is a new group created for Domain Access',
        }
        group_id = self.env['res.groups'].sudo().create(group_values)
        return group_id


class IrRule(models.Model):
    _inherit = "ir.rule"

    ks_domain_access_id = fields.Many2one('domain.access')
    custom = fields.Boolean(string='Custom Rule')

    def unlink(self):
        self.ks_domain_access_id.unlink(rule=True)
        group = self.groups
        res = super(IrRule, self).unlink()
        group.sudo().unlink()
        return res

    @api.model
    def _compute_domain(self, model_name, mode="read"):
        global_domains = []  # list of domains

        # add rules for parent models
        for parent_model_name, parent_field_name in self.env[model_name]._inherits.items():
            if domain := self._compute_domain(parent_model_name, mode):
                global_domains.append([(parent_field_name, 'any', domain)])

        rules = self._get_rules(model_name, mode=mode)
        if not rules:
            return expression.AND(global_domains) if global_domains else []

        # browse user and rules as SUPERUSER_ID to avoid access errors!
        eval_context = self._eval_context()
        user_groups = self.env.user.groups_id
        group_domains = []  # list of domains
        for rule in rules.sudo():
            # evaluate the domain for the current user
            dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
            dom = expression.normalize_domain(dom)
            # Evaluate custom group as a global group ( Word as AND condition)
            if rule.custom:
                profile = rule.ks_domain_access_id.ks_user_management_id
                env_user = self.env.user
                company_ids = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
                if company_ids:
                    for company_id in company_ids:
                        if profile.active and env_user.id in profile.ks_user_ids.ids and company_id in profile.ks_company_ids.ids:
                            global_domains.append(dom)
            elif not rule.groups:
                global_domains.append(dom)
            elif rule.groups & user_groups:
                group_domains.append(dom)

        # combine global domains and group domains
        if not group_domains:
            return expression.AND(global_domains)
        return expression.AND(global_domains + [expression.OR(group_domains)])
        # for rule in rules.sudo():
        #     # evaluate the domain for the current user
        #     dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
        #     dom = expression.normalize_domain(dom)
        #     custom_global_domain = False
        #     # Evaluate custom group as a global group ( Word as AND condition)
        #     if rule.custom:
        #         profile = rule.ks_domain_access_id.ks_user_management_id
        #         env_user = self.env.user
        #         company_ids = self._context.get('allowed_company_ids')
        #         if company_ids:
        #             for company_id in company_ids :
        #                 if profile.active and env_user.id in profile.ks_user_ids.ids and company_id in profile.ks_company_ids.ids:
        #                     custom_global_domain = True
        #     if not rule.groups or custom_global_domain:
        #         global_domains.append(dom)
        #     elif rule.groups & user_groups and not rule.custom:
        #         group_domains.append(dom)
        #
        # # combine global domains and group domains
        # if not group_domains:
        #     return expression.AND(global_domains)
        # return expression.AND(global_domains + [expression.OR(group_domains)])
