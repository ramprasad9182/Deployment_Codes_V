from odoo import fields, models, api, _
from odoo.exceptions import ValidationError



class AccountMove(models.Model):
    _inherit = 'account.move'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)
    ref_partner_ids = fields.Many2many('res.partner', string='Pat/Cust')
    nhcl_replication_status = fields.Boolean(string='Replication Status')
    picking_ref = fields.Char(string="Product Exchange POS")
    pos_bill_ref = fields.Char(string="Exchange POS Bill Ref")

    @api.model
    def default_get(self, fields_list):
        res = super(AccountMove, self).default_get(fields_list)
        if self._context.get('default_move_type') in ['out_invoice', 'out_refund']:
            cust = self.env['res.partner'].search([('group_contact.name', '=', 'Customer')])
            res['ref_partner_ids'] = cust
        elif self._context.get('default_move_type') in ['in_invoice', 'in_refund', 'in_receipt']:
            vend = self.env['res.partner'].search([('group_contact.name', '=', 'Vendor')])
            res['ref_partner_ids'] = vend
        return res

    def invoice_odt_report(self):
        self.ensure_one()
        return self.env.ref('nhcl_customizations.text_tiles_invoice_report_odt').report_action(self)

    def action_print_text_tiles_report(self):
        self.ensure_one()
        return self.env.ref('nhcl_customizations.text_tiles_invoice_report').report_action(self)
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cust_vend_ids = fields.Many2many('res.partner', string='Pat/Cust')

    @api.model
    def default_get(self, fields_list):
        res = super(AccountPayment, self).default_get(fields_list)
        if self._context.get('default_payment_type') in ['inbound']:
            cust = self.env['res.partner'].search([('group_contact.name', '=', 'Customer')])
            res['cust_vend_ids'] = cust
        elif self._context.get('default_payment_type') in ['outbound']:
            vend = self.env['res.partner'].search([('group_contact.name', '=', 'Vendor')])
            res['cust_vend_ids'] = vend
        return res


class AccountAccount(models.Model):
    _inherit = "account.account"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)


class AccountTax(models.Model):
    _inherit = 'account.tax'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        payments = super()._create_payments()  # Call Odoo's original function
        # Deduct the payment amount from the partner's wallet
        for payment in payments:
            partner = payment.partner_id
            if partner and hasattr(partner, 'wallet_amount'):
                if partner.wallet_amount < payment.amount:
                    raise ValidationError(_('The wallet amount for %s is insufficient to process this payment.') % partner.name)
                main_partner = self.env['res.partner.credit.note'].sudo().search([('partner_id','=',partner.id),('voucher_number','=',payment.ref)])
                main_partner.deducted_amount += payment.amount
                partner.wallet_amount -= payment.amount
        return payments
