# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.http import request
from odoo.addons.base.models.ir_ui_view import NameManager


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def _postprocess_tag_label(self, node, name_manager, node_info):
        """Hide label when the field is hidden inside profile management"""
        label_node = super(IrUiView, self)._postprocess_tag_label(node, name_manager, node_info)
        company_lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
        hidden_fields = self.env['field.access'].sudo().search(
            [('ks_model_id.model', '=', self.model),
             ('ks_user_management_id.active', '=', True),
             ('ks_user_management_id.ks_user_ids', 'in', self._uid),
             ('ks_user_management_id.ks_company_ids', 'in', company_lst)
             ])
        for hide_field in hidden_fields:
            for field_id in hide_field.ks_field_id:
                if (node.get('name') == field_id.name) or (
                        node.tag == 'label' and 'for' in node.attrib.keys() and node.attrib['for'] == field_id.name):
                    if hide_field.ks_field_invisible:
                        node_info['invisible'] = True
                        node.set('invisible', '1')
        return label_node

    # def _postprocess_tag_field(self, node, name_manager, node_info):
    #     """Hide field which is selected inside profile management"""
    #     """ make field [Required, Invisible and Read-only] which is selected inside user management"""
    #     field_node = super(IrUiView, self)._postprocess_tag_field(node, name_manager, node_info)
    #     company_lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
    #     if node.tag == 'field':
    #         hidden_fields = self.env['field.access'].sudo().search(
    #             [('ks_model_id.model', '=', name_manager.model._name),
    #              ('ks_user_management_id.active', '=', True),
    #              ('ks_user_management_id.ks_user_ids', 'in', self._uid),
    #              ('ks_user_management_id.ks_company_ids', 'in', company_lst)
    #              ])
    #         for hide_field in hidden_fields:
    #             for field_id in hide_field.ks_field_id:
    #                 if (node.tag == 'field' and node.get('name') == field_id.name):
    #                     if hide_field.ks_field_invisible:
    #                         node_info['invisible'] = True
    #                         node.set('invisible', '1')
    #                     if hide_field.ks_field_readonly:
    #                         node_info['readonly'] = True
    #                         node.set('readonly', '1')
    #                         node.set('force_save', '1')
    #                     if hide_field.ks_field_required:
    #                         node_info['required'] = True
    #                         node.set('required', '1')
    #     return field_node

    # def _postprocess_tag_button(self, node, name_manager, node_info):
    #     """Hide button which is selected inside profile management/button tab access"""
    #     if self.type != 'kanban':
    #         button_node = getattr(super(IrUiView, self), '_postprocess_tag_button', False)
    #         if button_node:
    #             super(IrUiView, self)._postprocess_tag_button(node, name_manager, node_info)
    #
    #         hide = None
    #         company_lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
    #         hide_button_ids = self.env['button.tab.access'].sudo().search([
    #             ('ks_model_id.model', '=', name_manager.model._name), ('ks_user_management_id.active', '=', True),
    #             ('ks_user_management_id.ks_user_ids', 'in', self._uid),
    #             ('ks_user_management_id.ks_company_ids', 'in', company_lst)])
    #
    #         # Filtered with same env user and current model
    #         hidden_buttons = hide_button_ids.mapped('ks_hide_button_ids')
    #         if hidden_buttons:
    #             for btn in hidden_buttons:
    #                 if btn.ks_name == node.get('name'):
    #                     if node.get('string'):
    #                         if _(btn.ks_tab_button_string) == node.get('string'):
    #                             hide = [btn]
    #                             break
    #                     else:
    #                         hide = [btn]
    #                         break
    #         if hide:
    #             node.set('invisible', '1')
    #             if 'attrs' in node.attrib.keys() and node.attrib['attrs']:
    #                 del node.attrib['attrs']
    #             node_info['invisible'] = True
    #
    #         return None
    #     else:
    #         getattr(super(IrUiView, self), '_postprocess_tag_button', False)

    # def _postprocess_tag_page(self, node, name_manager, node_info):
    #     """Hide tab which is selected inside profile management"""
    #     postprocessor = getattr(super(IrUiView, self), '_postprocess_tag_page', False)
    #     if postprocessor:
    #         super(IrUiView, self)._postprocess_tag_page(node, name_manager, node_info)
    #
    #     hide = None
    #     company_lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
    #     hide_tab_ids = self.env['button.tab.access'].sudo().search(
    #         [('ks_model_id.model', '=', name_manager.model._name),
    #          ('ks_user_management_id.active', '=', True),
    #          ('ks_user_management_id.ks_user_ids', 'in', self._uid),
    #          ('ks_user_management_id.ks_company_ids', 'in', company_lst)])
    #
    #     tabs_ids = hide_tab_ids.mapped('ks_hide_tab_ids')
    #     if tabs_ids:
    #         for tab in tabs_ids:
    #             if _(tab.ks_tab_button_string) == node.get('string'):
    #                 if node.get('name'):
    #                     if tab.ks_name == node.get('name'):
    #                         hide = [tab]
    #                         break
    #                 else:
    #                     hide = [tab]
    #                     break
    #     if hide:
    #         node.set('invisible', '1')
    #         if 'attrs' in node.attrib.keys() and node.attrib['attrs']:
    #             del node.attrib['attrs']
    #
    #         node_info['invisible'] = True
    #
    #     return None

    # def _postprocess_tag_filter(self, node, name_manager, node_info):
    #     """Hide filter which is selected inside profile management"""
    #     filter_group_node = getattr(super(IrUiView, self), '_postprocess_tag_filter', False)
    #     if filter_group_node:
    #         super(IrUiView, self)._postprocess_tag_filter(node, name_manager, node_info)
    #
    #     hide = None
    #     company_lst = [int(x) for x in request.httprequest.cookies.get('cids').split(',')]
    #     hide_filter_ids = self.env['filter.group.access'].sudo().search(
    #         [('ks_model_id.model', '=', name_manager.model._name),
    #          ('ks_user_management_id.active', '=', True),
    #          ('ks_user_management_id.ks_user_ids', 'in', self._uid),
    #          ('ks_user_management_id.ks_company_ids', 'in',
    #           company_lst)])
    #
    #     filter_ids = hide_filter_ids.mapped('ks_hide_filter_ids')
    #     if filter_ids:
    #         for filter in filter_ids:
    #             if _(filter.ks_filter_group_string) == node.get('string'):
    #                 if node.get('name'):
    #                     if filter.ks_filter_group_name == node.get('name'):
    #                         hide = [filter]
    #                         break
    #                 else:
    #                     hide = [filter]
    #                     break
    #     hide_group_ids = self.env['filter.group.access'].sudo().search(
    #         [('ks_model_id.model', '=', name_manager.model._name),
    #          ('ks_user_management_id.active', '=', True),
    #          ('ks_user_management_id.ks_user_ids', 'in', self._uid),
    #          ('ks_user_management_id.ks_company_ids', 'in',
    #           company_lst)])
    #     group_ids = hide_group_ids.mapped('ks_hide_group_ids')
    #     if group_ids:
    #         for group in group_ids:
    #             if _(group.ks_filter_group_string) == node.get('string'):
    #                 if node.get('name'):
    #                     if group.ks_filter_group_name == node.get('name'):
    #                         hide = [group]
    #                         break
    #                 else:
    #                     hide = [group]
    #                     break
    #     if hide:
    #         node.set('invisible', '1')
    #         if 'attrs' in node.attrib.keys() and node.attrib['attrs']:
    #             del node.attrib['attrs']
    #
    #         node_info['invisible'] = True
    #
    #     return None
