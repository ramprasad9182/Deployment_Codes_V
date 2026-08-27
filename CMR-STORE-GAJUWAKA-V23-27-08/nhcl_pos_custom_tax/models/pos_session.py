# -*- coding: utf-8 -*-
# Copyright (C) NextFlowIT

from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.session"

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("max_amount")
        res["search_params"]["fields"].append("min_amount")
        res["search_params"]["fields"].append("children_tax_ids")
        return res

    def _loader_params_loyalty_program(self):
        res = super()._loader_params_loyalty_program()
        res["search_params"]["fields"].append("is_active")
        return res

    def _loader_params_loyalty_rule(self):
        res = super()._loader_params_loyalty_rule()
        res["search_params"]["fields"].append("serial_ids")
        res["search_params"]["fields"].append("type_filter")
        return res

    def _loader_params_loyalty_reward(self):
        res = super()._loader_params_loyalty_reward()
        res["search_params"]["fields"].append("discount_product_id")
        res["search_params"]["fields"].append("cmr_discount_product_ids")
        res["search_params"]["fields"].append("product_price")
        res["search_params"]["fields"].append("buy_with_reward_price")
        res["search_params"]["fields"].append("reward_price")
        res["search_params"]["fields"].append("buy_product_value")
        res["search_params"]["fields"].append("ref_loyalty_rule_id")
        res["search_params"]["fields"].append("cheapest_qty")
        return res

    def _loader_params_res_company(self):
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['street', 'street2', 'city', 'zip']
        return vals

    def _get_pos_ui_hr_employee(self, params):
        params['search_params']['fields'] += ['barcode']
        employees = self.env['hr.employee'].search_read(**params['search_params'])
        employee_ids = [employee['id'] for employee in employees]
        user_ids = [employee['user_id'] for employee in employees if employee['user_id']]
        manager_ids = self.env['res.users'].browse(user_ids).filtered(
            lambda user: self.config_id.group_pos_manager_id in user.groups_id).mapped('id')

        employees_barcode_pin = self.env['hr.employee'].browse(employee_ids).get_barcodes_and_pin_hashed()
        bp_per_employee_id = {bp_e['id']: bp_e for bp_e in employees_barcode_pin}
        for employee in employees:
            if employee['user_id'] and employee['user_id'] in manager_ids or employee[
                'id'] in self.config_id.advanced_employee_ids.ids:
                employee['role'] = 'manager'
            else:
                employee['role'] = 'cashier'
            # employee['barcode_str'] = bp_per_employee_id[employee['id']]['barcode_str']
            employee['barcode_str'] = employee['barcode']
            employee['barcode'] = bp_per_employee_id[employee['id']]['barcode']
            employee['pin'] = bp_per_employee_id[employee['id']]['pin']

        return employees
