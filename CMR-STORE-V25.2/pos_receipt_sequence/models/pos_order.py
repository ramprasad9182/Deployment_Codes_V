from odoo import models, api, fields
import pytz
import re

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def create_pos_receipt_sequence(self,session_id):
        pos_session = self.env['pos.session'].browse(session_id)
        return pos_session.config_id.sale_receipt_sequence_id._next()

    def _export_for_ui(self, order):
        timezone = pytz.timezone(self._context.get("tz") or self.env.user.tz or "UTC")
        return {
            "lines": [[0, 0, line] for line in order.lines.export_for_ui()],
            "statement_ids": [
                [0, 0, payment] for payment in order.payment_ids.export_for_ui()
            ],
            "name": order.pos_reference,
            "uid": re.search("([0-9-]){14}", order.pos_reference).group(0)
            if not order.config_id.sale_receipt_sequence_id
            else order.pos_reference,
            "amount_paid": order.amount_paid,
            "amount_total": order.amount_total,
            "amount_tax": order.amount_tax,
            "amount_return": order.amount_return,
            "pos_session_id": order.session_id.id,
            "pricelist_id": order.pricelist_id.id,
            "partner_id": order.partner_id.id,
            "user_id": order.user_id.id,
            "sequence_number": order.sequence_number,
            "date_order": str(order.date_order.astimezone(timezone)),
            "fiscal_position_id": order.fiscal_position_id.id,
            "to_invoice": order.to_invoice,
            "shipping_date": order.shipping_date,
            "state": order.state,
            "account_move": order.account_move.id,
            "id": order.id,
            "is_tipped": order.is_tipped,
            "tip_amount": order.tip_amount,
            "access_token": order.access_token,
            "ticket_code": order.ticket_code,
            "last_order_preparation_change": order.last_order_preparation_change,
        }
