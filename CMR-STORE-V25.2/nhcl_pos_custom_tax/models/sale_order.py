import random
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    """ Add fields used to define some Brazilian taxes """
    _inherit = 'sale.order'

    disco = fields.Float('disc')

    @api.onchange('partner_id', 'order_line')
    def trigger_the_compute_tax_id(self):
        for rec in self:
            rec.order_line._compute_tax_id()

    def button_to_reset_discount(self):
        discount_product_line = self.order_line.filtered(lambda x: x.product_id.name == 'Discount')
        if discount_product_line:
            self.disco = 0
            self.order_line._compute_tax_id()
            discount_product_line.unlink()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('price_unit', 'discount')
    def trigger_the_compute_tax_id(self):
        for rec in self:
            rec._compute_tax_id()

    def unlink(self):
        if self.product_id.name == 'Discount' and self.order_id.disco > 0:
            raise ValidationError(
                _("You are not allowed to unlink Discount Product, if want to remove discount use Reset Discount Button"))
        else:
            return super(SaleOrderLine, self).unlink()
    @api.depends('product_id', 'company_id', 'price_unit', 'order_id.partner_id', 'discount','order_id.so_type')
    def _compute_tax_id(self):
        lines_by_company = defaultdict(lambda: self.env['sale.order.line'])
        cached_taxes = {}
        for line in self:
            # Check if 'so_type' is 'intra_state' and clear taxes
            if line.order_id.so_type == 'intra_state':
                line.tax_id = False
                continue  # Skip tax computation for this line
            lines_by_company[line.company_id] += line
        for company, lines in lines_by_company.items():
            for line in lines.with_company(company):
                taxes = None
                if line.product_id:
                    taxes = line.product_id.taxes_id._filter_taxes_by_company(company)
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
                if not line.product_id or not taxes:
                    # Nothing to map
                    line.tax_id = False
                    continue
                fiscal_position = line.order_id.fiscal_position_id
                cache_key = (fiscal_position.id, company.id, tuple(taxes.ids))
                cache_key += line._get_custom_compute_tax_cache_key()
                if cache_key in cached_taxes:
                    result = cached_taxes[cache_key]
                else:
                    result = fiscal_position.map_tax(taxes)
                    cached_taxes[cache_key] = result

                line.tax_id = result

class SaleOrderDiscount(models.TransientModel):
    _inherit = 'sale.order.discount'

    def _create_discount_lines(self):
        """Create SOline(s) according to wizard configuration"""
        self.ensure_one()
        discount_product = self._get_discount_product()

        if self.discount_type == 'amount':
            vals_list = [
                self._prepare_discount_line_values(
                    product=discount_product,
                    amount=self.discount_amount,
                    taxes=self.env['account.tax'],
                )
            ]
        else:  # so_discount
            total_price_per_tax_groups = defaultdict(float)
            for line in self.sale_order_id.order_line:
                if not line.product_uom_qty or not line.price_unit:
                    continue

                total_price_per_tax_groups[line.tax_id] += line.price_total

            if not total_price_per_tax_groups:
                # No valid lines on which the discount can be applied
                return
            elif len(total_price_per_tax_groups) == 1:
                # No taxes, or all lines have the exact same taxes
                taxes = next(iter(total_price_per_tax_groups.keys()))
                subtotal = total_price_per_tax_groups[taxes]
                vals_list = [{
                    **self._prepare_discount_line_values(
                        product=discount_product,
                        amount=subtotal * self.discount_percentage,
                        taxes=taxes,
                        description=_(
                            "Discount: %(percent)s%%",
                            percent=self.discount_percentage * 100
                        ),
                    ),
                }]
            else:
                vals_list = [
                    self._prepare_discount_line_values(
                        product=discount_product,
                        amount=subtotal * self.discount_percentage,
                        taxes=taxes,
                        description=_(
                            "Discount: %(percent)s%%"
                            "- On products with the following taxes %(taxes)s",
                            percent=self.discount_percentage * 100,
                            taxes=", ".join(taxes.mapped('name'))
                        ),
                    ) for taxes, subtotal in total_price_per_tax_groups.items()
                ]
        return self.env['sale.order.line'].create(vals_list)

    def action_apply_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        if self.discount_type == 'sol_discount':
            self.sale_order_id.order_line.write({'discount': self.discount_percentage * 100})
            self.sale_order_id.order_line._compute_tax_id()
        elif self.discount_type == 'amount':
            raise ValidationError(_("Fixed Amount Discount is not applicable, Please change another Discount Type"))
        else:
            self.sale_order_id.write({'disco': self.discount_percentage * 100})
            self.sale_order_id.order_line._compute_tax_id()
            self._create_discount_lines()

class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    @api.constrains("program_type", "date_from", "date_to")
    def _check_promotion_dates_required(self):
        for rec in self:
            if rec.program_type == "promotion":
                if not rec.date_from or not rec.date_to:
                    raise ValidationError(
                        _("Start Date and End Date are required for Promotion programs.")
                    )

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _ensure_unique_pos_reference(self, vals):
        ref = vals.get('pos_reference')
        if not ref:
            return vals

        # Check if this reference already exists in the database
        existing_order = self.search_count([('pos_reference', '=', ref)])

        if existing_order:
            # Standard way: Append the session ID or a random suffix
            # to make it unique without needing an ir.sequence
            session_id = vals.get('session_id')
            suffix = random.randint(1000, 9999)

            # Result example: 'Order 00001-001-0001' becomes 'Order 00001-001-0001-1-5829'
            vals['pos_reference'] = f"{ref}-{session_id}-{suffix}"

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Only apply logic if pos_reference is provided (standard for POS UI)
            if vals.get('pos_reference'):
                vals = self._ensure_unique_pos_reference(vals)
        return super().create(vals_list)