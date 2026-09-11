# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def _default_payment_method(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            order_id = self.env['pos.order'].browse(active_id)
            cash_methods = order_id.session_id.payment_method_ids.filtered(
                lambda pm: pm.is_cash_count or pm.type == 'cash'
            )
            if cash_methods:
                return cash_methods[0]
        return super()._default_payment_method()

    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Payment Method',
        required=True,
        default=_default_payment_method,
    )

    def check(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['pos.order'].browse(active_id)
            is_refund = (
                order.amount_total < 0 or
                sum(order.lines.mapped('price_subtotal_incl')) < 0 or
                bool(order.refunded_order_ids) or
                any(line.qty < 0 for line in order.lines)
            )
            if is_refund:
                ctx = dict(self.env.context, from_pos_make_payment_refund=True)
                res = super(PosMakePayment, self.with_context(ctx)).check()
                if order.state in {'paid', 'done'} and not order.account_move:
                    order.with_context(from_pos_make_payment_refund=True).action_pos_order_invoice()
                return res
        return super().check()
