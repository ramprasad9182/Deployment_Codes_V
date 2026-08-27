from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    """ Add fields used to define some Brazilian taxes """
    _inherit = 'purchase.order'

    disco = fields.Float('disc')

    @api.onchange('partner_id', 'order_line')
    def trigger_the_compute_tax_id(self):
        self.ensure_one()
        self.order_line._compute_tax_id()

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('price_unit', 'discount')
    def trigger_the_compute_tax_id(self):
        self.ensure_one()
        self._compute_tax_id()

    def unlink(self):
        for line in self:
            if line.product_id.name == 'Discount' and line.order_id.disco > 0:
                raise UserError(
                    _("You are not allowed to unlink Discount Product. To remove the discount, use the Reset Discount button."))
        return super(PurchaseOrderLine, self).unlink()

    @api.depends('product_id', 'company_id', 'price_unit', 'order_id.partner_id', 'discount','order_id.nhcl_po_type')
    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            if line.order_id.nhcl_po_type == 'intra_state':
                line.taxes_id = False
                continue
            fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id._get_fiscal_position(
                line.order_id.partner_id)
            # filter taxes by company
            taxes = line.product_id.supplier_taxes_id._filter_taxes_by_company(line.company_id)
            if len(taxes) >= 2:
                for tax in taxes:
                    if line.discount > 0:
                        if tax.min_amount <= line.price_unit * (
                                1 - line.discount / 100) <= tax.max_amount:
                            taxes = tax
                            break

                    else:
                        if tax.min_amount <= line.price_unit * (
                                1 - line.order_id.disco / 100) <= tax.max_amount:
                            taxes = tax
                            break
            line.taxes_id = fpos.map_tax(taxes)

