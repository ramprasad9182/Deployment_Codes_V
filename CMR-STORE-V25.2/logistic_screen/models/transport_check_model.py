from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TransportCheck(models.Model):
    _name = 'transport.check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "transport check"

    logistic_entry_number = fields.Char(string="Logistic Entry Number",readonly=True, copy=False, tracking=True)
    logistic_lr_date = fields.Date(string="Logistic LR Date", copy=False, tracking=True)
    logistic_lr_number = fields.Char(string="Logistic LR Number", copy=False, tracking=True)
    logistic_date = fields.Date(string="Logistic Date", copy=False, tracking=True)
    transporter = fields.Many2one('res.partner', 'Transporter', index=True, copy=False, tracking=True)
    consignment_number = fields.Char(string="Consignment", copy=False, tracking=True)
    po_order_id = fields.Many2one('purchase.order', string='Source PO', index=True, required=False,
                               ondelete='cascade', copy=False, tracking=True)
    product_id = fields.Many2one('product.template',string="Product", index=True, required=False, copy=False, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('cancel', 'Cancelled')], string='State'
        , copy=False, index=True, readonly=True,default='draft',
        store=True, tracking=True,
        help=" * Draft: The Transport check is not confirmed yet.\n"
             " * sent: Transport check verified and sent to Delivery Check.\n")
    no_of_bales = fields.Integer(string="No of Bales", tracking=True)
    item_details = fields.Text(string="Item Details", tracking=True, readonly=True)
    city = fields.Char(string="City", tracking=True)
    invoice_list = fields.Char(string="Invoice List", tracking=True)
    # zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)
    transport_entry_types = fields.Selection([('automatic', 'Automatic'),
                                              ('manual', 'Manual')], string="Logistic Type", copy=False,
                                             default='manual', )

    readonly_po_vendor = fields.Boolean(string="Readonly Flag",compute="_compute_readonly_po_vendor")
    name = fields.Char(
        string="Transport No",
        copy=False,
        index=True,
        default=lambda self: _('New'),
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('transport.check') or _('New')
        return super().create(vals_list)

    @api.depends('transport_entry_types')
    def _compute_readonly_po_vendor(self):
        for rec in self:
            rec.readonly_po_vendor = rec.transport_entry_types == 'automatic'


    # @api.model
    # def default_get(self, fields_list):
    #     res = super(TransportCheck, self).default_get(fields_list)
    #     logistic_type = self.env.context.get('transport_entry_types', 'manual')
    #     if logistic_type == 'automatic':
    #         res['readonly_po_vendor'] = True
    #     else:
    #         res['readonly_po_vendor'] = False
    #     return res

    @api.model
    def get_transport_check_info(self):
        upcoming_lr = self.search_count([('state', '=', 'sent')])
        return {
            'upcoming_lr_count': upcoming_lr,
        }

    def logistic_transport_check(self):
        for rec in self:
            product_details = "\n".join(
                [line.product_id.display_name for line in rec.po_order_id.order_line]
            ) if rec.po_order_id else ''

            if rec.state == 'draft':
                rec.state = 'sent'

                delivery_vals = {
                    'logistic_entry_number': rec.logistic_entry_number,
                    'logistic_lr_date': rec.logistic_lr_date,
                    'logistic_date': rec.logistic_date,
                    'logistic_lr_number': rec.logistic_lr_number,
                    'no_of_bales': rec.no_of_bales,
                    'deliver_bales': rec.no_of_bales,
                    'transporter': rec.transporter.id,
                    'city': rec.city,
                    'product_id': rec.product_id.id,
                    'item_details': product_details,
                }

                if rec.po_order_id:
                    delivery_vals.update({
                        'po_order_id': rec.po_order_id.id,
                        # 'placements': rec.po_order_id.partner_id.vendor_zone.id
                        # if rec.po_order_id.partner_id.vendor_zone else False
                    })

                return self.env['delivery.check'].create(delivery_vals)

    def action_confirm(self):
        for rec in self:
            product_details = "\n".join(
                [line.product_id.display_name for line in rec.po_order_id.order_line]
            ) if rec.po_order_id else ''

            rec.state = 'sent'
            if rec.po_order_id:
                rec.po_order_id.ho_status = 'delivery'

            delivery_vals = {
                'logistic_entry_number': rec.logistic_entry_number,
                'logistic_lr_date': rec.logistic_lr_date,
                'logistic_date': rec.logistic_date,
                'logistic_lr_number': rec.logistic_lr_number,
                'no_of_bales': rec.no_of_bales,
                'deliver_bales': rec.no_of_bales,
                'overall_remaining_bales': rec.no_of_bales,
                'transporter': rec.transporter.id,
                'city': rec.city,
                'product_id': rec.product_id.id,
                'consignment_number': rec.consignment_number,
                'item_details': product_details,
                # 'placements': rec.zone_id.id,
                # 'zone_id': rec.zone_id.id,
                'delivery_entry_types': 'automatic' if rec.po_order_id else 'manual',

            }

            if rec.po_order_id:
                delivery_vals.update({
                    'po_order_id': rec.po_order_id.id,

                })

            self.env['delivery.check'].create(delivery_vals)
            self.env.cr.commit()

            if rec.po_order_id:
                return {
                    'name': 'Purchase',
                    'res_model': 'purchase.order',
                    'view_mode': 'form',
                    'type': 'ir.actions.act_window',
                    'res_id': rec.po_order_id.id,
                }
            else:
                return {'type': 'ir.actions.act_window_close'}

    def reset_to_draft(self):
        for rec in self:
            if not rec.po_order_id:
                if rec.state == 'sent':
                    rec.state = 'draft'

                delivery_check_data = self.env['delivery.check'].search([
                    ('logistic_entry_number', '=', rec.logistic_entry_number),
                    ('logistic_lr_date', '=', rec.logistic_lr_date),
                    ('logistic_lr_number', '=', rec.logistic_lr_number),
                    ('no_of_bales', '=', rec.no_of_bales),
                    ('consignment_number', '=', rec.consignment_number),
                ])
                delivery_check_data.unlink()
                continue

            picking_status = self.env['stock.picking'].sudo().search([
                ('origin', '=', rec.po_order_id.name)
            ])
            delivery_status = self.env['delivery.check'].search([
                ('logistic_entry_number', '=', rec.logistic_entry_number)
            ])

            if delivery_status and delivery_status.state == 'delivery':
                raise ValidationError("Cannot Reset: Record already confirmed.")

            if rec.state == 'sent':
                rec.state = 'draft'

            delivery_check_data = self.env['delivery.check'].search([
                ('po_order_id', '=', rec.po_order_id.id),
                ('logistic_lr_date', '=', rec.logistic_lr_date),
                ('logistic_lr_number', '=', rec.logistic_lr_number),
                ('no_of_bales', '=', rec.no_of_bales),
                ('consignment_number', '=', rec.consignment_number),
            ])
            delivery_check_data.unlink()







