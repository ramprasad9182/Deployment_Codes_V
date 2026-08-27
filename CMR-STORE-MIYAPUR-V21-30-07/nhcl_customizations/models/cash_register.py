from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
import pytz
from collections import defaultdict


class CashRegister(models.Model):
    _name = 'cash.register'
    _description = 'Cash Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string="Reference",required=True,
        copy=False,readonly=True,default=lambda self: _('New'))
    date = fields.Date(string="Date",default=fields.Date.context_today,required=True)
    requester_id = fields.Many2one('res.users',string="Requester",
        default=lambda self: self.env.user,required=True)
    company_id = fields.Many2one('res.company',string="Company",
        default=lambda self: self.env.company,required=True)
    line_ids = fields.One2many('cash.register.line','cash_register_id',string="Bills")
    register_line_ids = fields.One2many('cash.register.post.line','cash_register_id',string="Posting")
    total_amount = fields.Float(string="Total Amount",compute="_compute_totals",store=True, digits=(16, 2))
    total_discount = fields.Float(string="Total Discount", digits=(16, 2))
    state = fields.Selection([('draft', 'Draft'),
            ('confirmed', 'Confirmed'),('cancel', 'Cancelled')],
        string="Status", default='draft', tracking=True)
    register_type = fields.Selection([('cash_register', 'Cash Register'),
                              ('hsn_code', 'HSN Code'), ('time_stamp', 'Time Stamp')],
                             string="Type", default='cash_register', tracking=True)
    credit_note_id = fields.Many2one('account.move',string="Credit Note",readonly=True)
    from_range = fields.Integer(string="From Range")
    to_range = fields.Integer(string="To Range")
    global_discount = fields.Float(string="Discount %")
    global_discount_amount = fields.Float(string="Discount Amount")

    @api.depends('line_ids.bill_amount', 'line_ids.discount')
    def _compute_totals(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('bill_amount'))



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cash.register.seq') or _('New')

        return super(CashRegister, self).create(vals_list)

    def cash_customer_create_credit_note(self):
        for cash in self:
            total_discount = cash.total_discount
            if cash.total_discount <= 0:
                raise ValidationError(f"Discount must be greater than 0 for Bill.")
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('name', '=', 'Cash Discount')
            ], limit=1)
            if not journal:
                raise ValidationError("No journal found with type 'sale' and name 'Cash Discount'.")
            product = self.env.ref('nhcl_customizations.nhcl_product_product_cash_customer')
            partner = self.env.ref('nhcl_customizations.nhcl_public_partner')
            account = journal.default_account_id.id
            if not account:
                raise ValidationError(f"Income account not defined for journal {product.display_name}")
            if not total_discount:
                raise ValidationError("Total discount amount is zero. Credit note cannot be created.")
            credit_note_vals = {
                'move_type': 'out_refund',
                'partner_id': partner.id,
                'invoice_origin': cash.name,
                'currency_id': self.env.company.currency_id.id,
                'journal_id': journal.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': total_discount,
                    'name': "Cash Customer",
                    'account_id': account.id,
                })],
            }
            credit_note = self.env['account.move'].create(credit_note_vals)
            credit_note.action_post()
            cash.credit_note_id = credit_note.id
            cash.line_ids.mapped('pos_order_id').write({
                'is_cash_register_used': True
            })

    def create_hsn_credit_note(self):
        for cash in self:
            if not cash.register_line_ids:
                raise ValidationError("No register lines found to create credit note.")
            journal = self.env['account.journal'].search([('type', '=', 'sale'),('name', '=', 'Cash Discount')], limit=1)
            if not journal:
                raise ValidationError("No journal found with type 'sale' and name 'Cash Discount'.")
            product = self.env.ref('nhcl_customizations.nhcl_product_product_cash_customer')
            account = (product.property_account_income_id
                       or product.categ_id.property_account_income_categ_id)
            if not account:
                raise ValidationError(f"Income account not defined for product {product.display_name}")
            partner = self.env.ref('nhcl_customizations.nhcl_public_partner')
            invoice_lines = []
            for line in cash.register_line_ids:
                if line.amount <= 0:
                    continue
                product = line.product_template_id.product_variant_id
                taxes = product.taxes_id.filtered(lambda t: t.company_id == cash.company_id)

                selected_tax = self.env['account.tax']

                if len(taxes) == 1:
                    selected_tax = taxes
                else:
                    selected_tax = taxes.filtered(
                        lambda t: t.min_amount <= line.amount <= t.max_amount
                    )[:1]
                invoice_lines.append((0, 0, {
                    'product_id': line.product_template_id.product_variant_id.id,
                    'quantity': 1,
                    'price_unit': line.amount,
                    'name': line.product_template_id.product_variant_id.display_name,
                    'account_id': account.id,
                    'tax_ids': [(6, 0, selected_tax.ids)],
                }))
            if not invoice_lines:
                raise ValidationError("No valid lines to create credit note.")
            credit_note_vals = {
                'move_type': 'out_refund',
                'partner_id': partner.id,
                'invoice_origin': cash.name,
                'currency_id': self.env.company.currency_id.id,
                'journal_id': journal.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_line_ids': invoice_lines,
            }
            credit_note = self.env['account.move'].create(credit_note_vals)
            credit_note.action_post()
            cash.credit_note_id = credit_note.id


    def action_view_credit_note(self):
        self.ensure_one()
        if not self.credit_note_id:
            raise ValidationError("No credit note created.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.credit_note_id.id,
            'target': 'current',
        }


    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Please add at least one bill."))
            if rec.register_type == 'cash_register':
                rec.cash_customer_create_credit_note()
            elif rec.register_type == 'hsn_code':
                rec.create_hsn_credit_note()
            rec.state = 'confirmed'

    def action_cancel(self):
        self.state = 'cancel'

    def action_reset_to_draft(self):
        self.state = 'draft'

    def _get_day_range(self, date_value):
        # date_value = fields.Date (e.g. 2026-02-24)

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        # Start of day (00:00:00)
        start_dt = datetime.combine(date_value, time.min)
        start_dt = user_tz.localize(start_dt).astimezone(pytz.UTC)

        # End of day (23:59:59)
        end_dt = datetime.combine(date_value, time.max)
        end_dt = user_tz.localize(end_dt).astimezone(pytz.UTC)

        return start_dt, end_dt

    def nhcl_load_pos_orders(self):
        for rec in self:
            if rec.register_type == 'cash_register':
                existing = self.search([('id', '!=', rec.id),('date', '=', rec.date),('register_type','=','cash_register'),('state','!=','cancel')], limit=1)
                if existing:
                    raise ValidationError(f"POS orders already loaded for date {rec.date}.")
                # Clear lines
                rec.line_ids = [(5, 0, 0)]
                start_dt, end_dt = self._get_day_range(rec.date)
                # Get Cash payment method
                cash_method = self.env['pos.payment.method'].search([
                    ('name', '=', 'Cash')
                ], limit=1)

                if not cash_method:
                    return
                orders = self.env['pos.order'].search([
                    ('date_order', '>=', start_dt),
                    ('date_order', '<', end_dt),('amount_total','>',0.0),
                    ('payment_ids.payment_method_id', '=', cash_method.id),
                ])
                lines_vals = []
                orders = orders.filtered(
                    lambda o: all(p.payment_method_id.id == cash_method.id for p in o.payment_ids)
                )
                for order in orders:
                    lines_vals.append((0, 0, {
                        'pos_order_id': order.id,
                        'partner_id': order.partner_id.id,
                        'mobile': order.partner_id.mobile,
                        'bill_amount': order.amount_total,
                        'payment_amount': sum(order.payment_ids.mapped('amount')),
                    }))
                rec.line_ids = lines_vals
            elif rec.register_type == 'hsn_code':
                if rec.from_range < 1:
                    raise ValidationError("Please give more than 0 in from range.")
                elif rec.from_range > rec.to_range:
                    raise ValidationError("Please give to range more than from range.")
                elif rec.global_discount > 0 and rec.global_discount_amount > 0:
                    raise ValidationError("Please give discount amount or discount percent.")
                elif rec.global_discount <= 0 and rec.global_discount_amount <= 0:
                    raise ValidationError("Please give more than 0 in Discount percent.")
                elif rec.global_discount_amount <= 0 and rec.global_discount <= 0:
                    raise ValidationError("Please give more than 0 in Discount amount.")
                existing = self.search([
                    ('id', '!=', rec.id),
                    ('date', '=', rec.date),
                    ('register_type', '=', 'hsn_code'),
                    ('state', '!=', 'cancel')
                ], limit=1)
                if existing:
                    raise ValidationError(f"POS orders already loaded for date {rec.date}.")
                new_from = int(rec.from_range)
                new_to = int(rec.to_range)
                for line in rec.line_ids:
                    if line.cash_price_range:
                        old_from, old_to = map(int, line.cash_price_range.split('-'))
                        if new_from <= old_to and new_to >= old_from:
                            raise ValidationError(
                                f"Range {new_from}-{new_to} overlaps with existing range "
                                f"{old_from}-{old_to} in this record."
                            )
                start_dt, end_dt = self._get_day_range(rec.date)
                hsn_cash_method = self.env['pos.payment.method'].search([
                    ('name', '=', 'Cash')
                ], limit=1)
                orders = self.env['pos.order'].search([
                    ('date_order', '>=', start_dt),
                    ('date_order', '<', end_dt),
                    ('amount_total', '>', 0.0),
                ])
                orders = orders.filtered(
                    lambda o: all(p.payment_method_id.id == hsn_cash_method.id for p in o.payment_ids)
                              and (rec.from_range <= sum(p.amount for p in o.payment_ids) <= rec.to_range)
                )
                if not orders:
                    return

                lines = self.env['pos.order.line'].search([
                    ('order_id', 'in', orders.ids),
                    ('product_id.product_tmpl_id.l10n_in_hsn_code', '!=', False)
                ])

                hsn_data = defaultdict(lambda: {
                    'amount': 0.0,
                    'qty': 0.0,
                    'product_id': False,
                })
                for line in lines:
                    hsn = line.product_id.product_tmpl_id.l10n_in_hsn_code
                    key = (hsn, line.product_id.product_tmpl_id.id)  # <-- group by HSN + Product
                    hsn_data[key]['amount'] += line.price_subtotal_incl
                    hsn_data[key]['qty'] += line.qty
                    hsn_data[key]['product_id'] = line.product_id.product_tmpl_id.id
                lines_vals = []
                range_value = f"{int(rec.from_range)}-{int(rec.to_range)}"
                for (hsn, product_id), values in hsn_data.items():
                    lines_vals.append((0, 0, {
                        'hsn_code': hsn,
                        'product_template_id': product_id,
                        'bill_amount': values['amount'],
                        'quantity': values['qty'],
                        'discount': rec.global_discount,
                        'discount_amount': rec.global_discount_amount,
                    }))
                rec.line_ids = lines_vals
                discount_lines = rec.line_ids.filtered(lambda l: l.discount > 0)
                discount_amount_lines = rec.line_ids.filtered(lambda l: l.discount_amount > 0)
                if discount_lines:
                    discount_lines._onchange_discount()
                if discount_amount_lines:
                    discount_amount_lines._onchange_discount_amount()
                rec.from_range = rec.to_range = rec.global_discount = rec.global_discount_amount = False

    def copy_to_register_lines(self):
        for rec in self:
            rec.register_line_ids.unlink()
            selected_lines = rec.line_ids.filtered(lambda l: l.nhcl_select)
            if not selected_lines:
                raise ValidationError("Please select at least one line.")
            new_lines = []
            for line in selected_lines:
                # Find service product with same name
                service_product = self.env['product.template'].search([
                    ('name', '=', line.product_template_id.name),
                    ('detailed_type', '=', 'service'),('default_code','!=',False),
                ], limit=1)
                if not service_product:
                    raise ValidationError(f'Product {line.product_template_id.name} is not available here.')
                new_lines.append((0, 0, {
                    'product_template_id': service_product.id,
                    'amount': line.discount_amount,
                    'hsn_code': line.hsn_code,
                }))
            rec.register_line_ids = new_lines



class CashRegisterLine(models.Model):
    _name = 'cash.register.line'
    _description = 'Cash Register Line'

    cash_register_id = fields.Many2one('cash.register',string="Cash Register",ondelete='cascade')
    pos_order_id = fields.Many2one('pos.order',string="Bill Number")
    partner_id = fields.Many2one('res.partner',string="Customer Name")
    product_id = fields.Many2one('product.product',string="Item")
    product_template_id = fields.Many2one('product.template',string="Item")
    mobile = fields.Char(string="Mobile")
    bill_amount = fields.Float(string="Bill Amount", digits=(16, 2))
    discount = fields.Float(string="Discount %", digits=(16, 2))
    discount_amount = fields.Float(string="Discount Amount", digits=(16, 2))
    payment_amount = fields.Float(string="Payment Mode Amount", digits=(16, 2))
    quantity = fields.Float(string="Quantity", digits=(16, 2))
    hsn_code = fields.Char(string="HSN Code")
    nhcl_select = fields.Boolean(string="Select")
    amount = fields.Float(string="Amount", digits=(16, 2))
    cash_price_range = fields.Char(string="Cash Range")



    @api.constrains('pos_order_id')
    def _check_duplicate_pos_order(self):
        for rec in self:
            existing = self.search([
                ('pos_order_id', '=', rec.pos_order_id.id),
                ('id', '!=', rec.id)])
            if existing:
                raise ValidationError(f"This POS Order {rec.pos_order_id.pos_reference} is already used.")

    # -------------------------
    # Onchange Discount %
    # -------------------------
    @api.onchange('discount')
    def _onchange_discount(self):
        for rec in self:
            if rec.discount and rec.cash_register_id.register_type == 'hsn_code':
                if rec.discount < 0 or rec.discount > 100:
                    raise ValidationError("Discount percentage must be between 0 and 100.")
                discount_amount = (rec.bill_amount * rec.discount) / 100
                rec.amount = discount_amount

    # -------------------------
    # Onchange Discount Amount
    # -------------------------
    @api.onchange('discount_amount')
    def _onchange_discount_amount(self):
        for rec in self:
            if rec.discount_amount and rec.cash_register_id.register_type == 'hsn_code':
                if rec.discount_amount < 0:
                    raise ValidationError("Discount amount cannot be negative.")
                if rec.discount_amount > rec.bill_amount:
                    raise ValidationError("Discount amount cannot exceed bill amount.")
                # rec.discount = (rec.discount_amount / rec.bill_amount) * 100
                rec.amount = rec.discount_amount
            # if not rec.nhcl_select and rec.cash_register_id.register_type == 'hsn_code':
            #     raise ValidationError("Need to select before entering")

    # -------------------------
    # Constraint Safety Check
    # -------------------------
    @api.constrains('discount')
    def _check_discount_limit(self):
        for rec in self:
            if (rec.discount < 0 or rec.discount > 100) and rec.nhcl_select and rec.cash_register_id.register_type == 'hsn_code':
                raise ValidationError("Discount must be between 0 and 100.")


class CashRegisterPostLine(models.Model):
    _name = 'cash.register.post.line'
    _description = 'Cash Register Post Line'

    cash_register_id = fields.Many2one('cash.register',string="Cash Register",ondelete='cascade')
    product_id = fields.Many2one('product.product',string="Item")
    product_template_id = fields.Many2one('product.template', string="Item")
    amount = fields.Float(string="Amount", digits=(16, 2))
    hsn_code = fields.Char(string="HSN Code")