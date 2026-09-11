from odoo import models, fields


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if self.config_id.sale_receipt and self.config_id.sale_receipt_sequence_id:
            result.append('ir.sequence')
            result.append('ir.sequence.date_range')
        return result

    def _loader_params_ir_sequence(self):
        data = {
            'search_params': {
                'domain': [('id', '=', self.config_id.sale_receipt_sequence_id[0].id)],
            }
        }
        return data

    def _loader_params_ir_sequence_date_range(self):
        data2 =  {'search_params': {'domain': [], 'fields': ['date_from', 'date_to', 'number_next_actual']}}
        return data2

    def _get_pos_ui_ir_sequence(self, params):
        return self.env['ir.sequence'].search_read(**params['search_params'])

    def _get_pos_ui_ir_sequence_date_range(self, params):
        return self.env['ir.sequence.date_range'].search_read(**params['search_params'])