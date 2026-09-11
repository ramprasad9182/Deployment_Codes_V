from odoo import models,fields,api,_
from odoo.exceptions import ValidationError


class OpenParcel(models.Model):
    _name = 'open.parcel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Open Parcel'


    parcel_lr_no = fields.Char(string='LR Number', copy=False, tracking=True)
    parcel_bale = fields.Integer(string='Bale Qty', copy=False, tracking=True)
    parcel_rc_number = fields.Char(string='RC Number', copy=False, tracking=True)
    parcel_po_no = fields.Many2one('purchase.order',string='PO Number', copy=False, tracking=True)
    parcel_transporter = fields.Many2one('res.partner',string='Transporter', copy=False, domain=[('group_contact.name','=','Transporter')], tracking=True)
    state = fields.Selection([('draft', 'Draft'),('done', 'Open Parcel Done'),
        ('cancel', 'Cancelled')], string='State', copy=False, index=True, readonly=True, default='draft',store=True, tracking=True,
        help=" * Draft: The Open Parcel is not confirmed yet.\n"" * sent: Open Parcel is confirmed.\n")
    barcode = fields.Char(string="Barcode",copy=False)
    verified = fields.Boolean(string='Verified', copy=False)
    name = fields.Char(
        string="Parcel No",
        copy=False,
        index=True,
        default=lambda self: _('New'),
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = seq.next_by_code('open.parcel') or _('New')
        return super().create(vals_list)

    @api.model
    def get_open_parcel_info(self):
        open_parcel = self.search_count([('state', '=', 'done')])
        return {
            'open_parcel': open_parcel,
        }


    def open_parcel(self):
        for rec in self:
            if rec.state == 'draft':
                rec.write({'verified': True})
                if rec.verified:
                    rec.state = 'done'

    def open_parcel_check(self):
        for rec in self:
            rec.write({'verified': True})
            if rec.verified:
                rec.state = 'done'

    def open_parcel_done(self):
        pass


    def reset_open_parcel(self):
        for rec in self:
            rec.write({'verified': False})
            if not rec.verified:
                rec.state = 'draft'





