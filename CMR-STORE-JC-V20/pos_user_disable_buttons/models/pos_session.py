# -*- coding: utf-8 -*-
from odoo import models
class InheritPosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_users(self):
        result = super()._loader_params_res_users()
        result['search_params']['fields'].append('allow_discount_button')
        result['search_params']['fields'].append('allow_numpad_button')
        result['search_params']['fields'].append('allow_plusminus_button')
        result['search_params']['fields'].append('allow_qty_button')
        result['search_params']['fields'].append('allow_customer_selection')
        result['search_params']['fields'].append('allow_remove_button')
        result['search_params']['fields'].append('allow_price_button')
        result['search_params']['fields'].append('allow_payment_button')
        result['search_params']['fields'].append('allow_refund_button')
        result['search_params']['fields'].append('allow_new_order_button')
        result['search_params']['fields'].append('allow_delete_order_button')
        result['search_params']['fields'].append('allow_re_print_button')
        # result['search_params']['fields'].append('allow_global_discount')
        # result['search_params']['fields'].append('allow_amount_discount')
        # result['search_params']['fields'].append('allow_selected_lines_discount')
        return result
