from odoo import http
from odoo.http import request

class PosOrderController(http.Controller):

    @http.route('/api/loyalty.program/call_action',
                type='json',
                auth='public',
                methods=['POST'],
                csrf=False)
    def pos_order_invoice(self, **kwargs):

        program_id = kwargs.get('program_id')

        if not program_id:
            return {
                'success': False,
                'message': 'program_id is required'
            }

        ho_store = request.env['nhcl.ho.store.master'].sudo().search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ], limit=1)

        store_promo = request.env['loyalty.program'].sudo().browse(program_id)

        if not store_promo.exists():
            return {
                'success': False,
                'message': 'Loyalty Program not found'
            }

        try:
            serial_count = 0
            for rule in store_promo.rule_ids:
                rule.update_loyalty_serials()
                line_count = len(rule.serial_ids)

            return {
                'success': True,
                'message': 'Loyalty rules updated successfully'
            }

        except Exception as e:
            ho_store.create_cmr_transaction_replication_log(
                'Promotions',
                store_promo.id,
                store_promo.name,
                500,
                'add',
                'failure',
                str(e)
            )
            return {
                'success': False,
                'message': str(e)
            }