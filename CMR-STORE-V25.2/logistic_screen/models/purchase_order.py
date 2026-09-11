from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # logistic_count = fields.Integer(string="Count", compute='_compute_logistic_count')
    ho_status = fields.Selection(
        [('logistic', 'Logistic Entry'), ('transport', 'Transport Check'),
         ('delivery', 'Delivery Check')], string='Logistic Status', tracking=True)

    # def _compute_logistic_count(self):
    #     self.logistic_count = self.env['logistic.screen.data'].search_count(
    #         [('po_number', '=', self.id)])
    #
    # def logistic_screen_button(self):
    #     for record in self:
    #         domain = [('po_number', '=', record.id)]
    #
    #         return {
    #             'name': 'Logistic Entry',
    #             'res_model': 'logistic.screen.data',
    #             'view_mode': 'tree,form',
    #             'type': 'ir.actions.act_window',
    #             'domain': domain,
    #         }
    #
    # def button_approve(self, force=False):
    #     res = super(PurchaseOrder, self).button_approve()
    #     # if self.order_line.filtered(lambda x:x.price_unit <= 0):
    #     #     raise ValidationError("Unit Price should not be zero")
    #     # logistic_seq = self.env['nhcl.master.sequence'].search(
    #     #     [('nhcl_code', '=', 'logistic.screen.data'), ('nhcl_state', '=', 'activate')], limit=1)
    #     # if not logistic_seq:
    #     #     raise exceptions.ValidationError(
    #     #         _("Configure the Logistic Screen Sequence in Settings to perform this action."))
    #
    #     for order in self:
    #         if order.nhcl_po_type == 'ho_operation':
    #             # zone_ids = order.order_line.mapped('zone_id')
    #             # unique_zone_ids = set(zone_ids)
    #             # if len(unique_zone_ids) == 1:
    #             #     zone_id = list(unique_zone_ids)[0]
    #             #     if zone_id:
    #             order.ho_status = 'logistic'
    #             self.env['logistic.screen.data'].create({
    #                 'vendor': order.partner_id.id,
    #                 'po_number': order.id,
    #                 'gst_no': order.partner_id.vat,
    #                 'no_of_quantity': order.sum_of_quantites,
    #                 'consignor': order.partner_id.id,
    #                 # 'zone_id': zone_id.id,
    #                 'logistic_entry_types': 'automatic',
    #                 'logistic_vendor': order.logistic_vendor.id
    #             })
    #     return res
