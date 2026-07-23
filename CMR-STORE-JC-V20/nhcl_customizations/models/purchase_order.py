from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from odoo.tools.float_utils import float_compare


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'



    po_approval = fields.Integer("Approval")
    state = fields.Selection([
        ('draft', 'Purchase Indent'),
        ('sent', 'Purchase Indent Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', tracking=True)
    nhcl_po_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('inter_state','Inter State'), ('intra_state', 'Intra State'), ('others', 'Others')],
        string='PO Type', tracking=True)
    dummy_po_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),
         ('others', 'Others')], string='Dummy PO Type', compute='_onchange_nhcl_po_type')
    start_date = fields.Date(string='Start Date', copy=False, tracking=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date', copy=False, tracking=True)
    due_days = fields.Integer(string='Due days', copy=False, tracking=True, compute='_compute_due_days', store=True)
    renewal_date = fields.Date(string='Renewal Date', copy=False, tracking=True)
    advt_status = fields.Selection(
        [('new', 'New'), ('closed', 'Closed'),
         ('renewed', 'Renewed')], string='Advt. Status', tracking=True, copy=False)
    nhcl_store_status = fields.Boolean(string='Ho Status', tracking=True, copy=False)





    @api.depends('nhcl_po_type')
    def _onchange_nhcl_po_type(self):
        for i in self:
            if i.nhcl_po_type == 'ho_operation':
                i.dummy_po_type = 'ho_operation'
            elif i.nhcl_po_type == 'advertisement':
                i.dummy_po_type = 'advertisement'
            elif i.nhcl_po_type == 'others':
                i.dummy_po_type = 'others'
            elif i.nhcl_po_type == 'inter_state':
                i.dummy_po_type = 'ho_operation'
            elif i.nhcl_po_type == 'intra_state':
                i.dummy_po_type = 'ho_operation'
            else:
                i.dummy_po_type = ''

    @api.constrains('order_line')
    def _check_same_product_category(self):
        for order in self:
            category_id = None
            for line in order.order_line:
                product = line.product_id
                if not product or not product.categ_id:
                    continue  # Skip lines with no product or no category
                if category_id is None:
                    category_id = product.categ_id.id
                elif product.categ_id.id != category_id:
                    raise ValidationError(
                        _("All products in this Purchase Order must belong to the same product category."))

    @api.model
    def default_get(self, fields):
        res = super(PurchaseOrder, self).default_get(fields)
        king_partner = self.env['res.partner'].search([
            ('name', 'ilike', 'TEXTILE'),
        ], limit=1)

        if not king_partner:
            raise ValidationError("No TEXTILE related name not found in the vendors.")

        if king_partner:
            res['partner_id'] = king_partner.id
            if king_partner.state_id.id == self.env.company.state_id.id:
                res['nhcl_po_type'] = 'intra_state'
            else:
                res['nhcl_po_type'] = 'inter_state'
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    serial_no = fields.Char(string="Serial No")
    product_id = fields.Many2one('product.product', string='Product Variant', domain=[('purchase_ok', '=', True), ('detailed_type', '!=', 'service')], change_default=True, index='btree_not_null')
    product_template_id = fields.Many2one(
        'product.template',
        string='Product',
        domain="[('purchase_ok', '=', True), ('detailed_type', '!=', 'service')]"
    )
    s_no = fields.Integer(string="S.No", compute="_compute_s_no")


    @api.depends('order_id')
    def _compute_s_no(self):
        for rec in self.order_id:
            for index, line in enumerate(rec.order_line, start=1):
                line.s_no = index

    @api.constrains('product_id')
    def _check_same_product_category(self):
        for line in self:
            if not line.product_id or not line.order_id:
                continue

            order = line.order_id
            categ_id = line.product_id.categ_id

            if not categ_id:
                continue

            other_lines = order.order_line.filtered(
                lambda l: l.id != line.id and l.product_id and l.product_id.categ_id
            )

            if other_lines:
                base_category = other_lines[0].product_id.categ_id
                if categ_id != base_category:
                    raise ValidationError(_(
                        "All products in this Purchase Order must belong to the same product category."
                    ))