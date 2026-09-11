from odoo import models, fields, api, _
import requests
from datetime import datetime, time, timedelta
from odoo.tools.float_utils import float_round
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclHSNTaxReport(models.Model):
    _name = 'nhcl.hsn.tax.report'
    _description = "hsn tax report main"
    _rec_name = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return datetime.combine(today, time.min) - timedelta(hours=5, minutes=30)

    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return datetime.combine(today, time.max) - timedelta(hours=5, minutes=30)


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_company_id = fields.Many2one('res.company', string='Store Name', default=lambda self: self.env.company)
    nhcl_pos_hsn_tax_ids = fields.One2many('nhcl.hsn.tax.report.line', 'nhcl_pos_hsn_tax_id')
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qtys')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Gross Total')
    total_taxable_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Net Total')
    total_cgst_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total CGST')
    total_sgst_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total SGST')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    name = fields.Char(string='Name', default='HSN Wise Tax Report')
    l10n_in_hsn_code = fields.Char(string="HSN/SAC Code", help="Harmonized System Nomenclature/Services Accounting Code")
    tax_id = fields.Many2one('account.tax', string='Tax')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_pos_hsn_tax_ids
            rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            rec.total_taxable_amount = sum(lines.mapped('nhcl_taxable_amount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_cgst_amount = sum(lines.mapped('nhcl_cgst_amount'))
            rec.total_sgst_amount = sum(lines.mapped('nhcl_sgst_amount'))
    #old
    # def get_hsn_with_tax_wise_report(self):
    #     self.nhcl_pos_hsn_tax_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         domain = [
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #             ('order_id.company_id', '=', store.nhcl_company_id.id),
    #             ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
    #         ]
    #
    #         # Filter by HSN code
    #         if self.l10n_in_hsn_code:
    #             domain.append((
    #                 'product_id.l10n_in_hsn_code',
    #                 '=',
    #                 self.l10n_in_hsn_code
    #             ))
    #
    #         # Filter by Tax
    #         if self.tax_id:
    #             domain.append((
    #                 'tax_ids',
    #                 'in',
    #                 self.tax_id.id
    #             ))
    #
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         grouped_data = {}
    #
    #         for line in pos_lines:
    #             product = line.product_id
    #             if not product:
    #                 continue
    #             categ = product.categ_id
    #
    #             family = ''
    #             category_name = ''
    #             class_name = ''
    #             brick_name = ''
    #
    #             if categ:
    #                 parent_ids = [
    #                     int(x)
    #                     for x in (categ.parent_path or '').rstrip('/').split('/')
    #                     if x
    #                 ]
    #
    #                 # 1st level → Family
    #                 if len(parent_ids) >= 1:
    #                     family_rec = self.env['product.category'].browse(parent_ids[0])
    #                     family = family_rec.name or ''
    #
    #                 # 2nd level → Category
    #                 if len(parent_ids) >= 2:
    #                     category_rec = self.env['product.category'].browse(parent_ids[1])
    #                     category_name = category_rec.name or ''
    #
    #                 # 3rd level → Class
    #                 if len(parent_ids) >= 3:
    #                     class_rec = self.env['product.category'].browse(parent_ids[2])
    #                     class_name = class_rec.name or ''
    #
    #                 # 4th level → Brick
    #                 if len(parent_ids) >= 4:
    #                     brick_rec = self.env['product.category'].browse(parent_ids[3])
    #                     brick_name = brick_rec.name or ''
    #
    #             hsn_code = product.l10n_in_hsn_code or 'N/A'
    #
    #             tax = line.tax_ids[:1]
    #             tax_name = tax.name if tax else 'No Tax'
    #
    #             qty = line.qty
    #             subtotal = line.price_subtotal
    #             subtotal_incl = line.price_subtotal_incl
    #             tax_amount = subtotal_incl - subtotal
    #
    #             key = (store.id, hsn_code, tax_name,product.id)
    #
    #             if key not in grouped_data:
    #                 grouped_data[key] = {
    #                     'family_rec': family,
    #                     'category_rec': category_name,
    #                     'class_rec': class_name,
    #                     'brick_rec': brick_name,
    #                     'product_id': product.id,
    #                     'qty': 0,
    #                     'taxable': 0.0,
    #                     'total': 0.0,
    #                     'tax': 0.0,
    #                     'cgst': 0.0,
    #                     'sgst': 0.0,
    #                 }
    #
    #             grouped_data[key]['qty'] += qty
    #             grouped_data[key]['taxable'] += subtotal
    #             grouped_data[key]['total'] += subtotal_incl
    #             grouped_data[key]['tax'] += tax_amount
    #             grouped_data[key]['cgst'] += tax_amount / 2
    #             grouped_data[key]['sgst'] += tax_amount / 2
    #
    #         vals_list = []
    #         for (store_id, hsn, tax_name,product_id), vals in grouped_data.items():
    #             vals_list.append({
    #                 'nhcl_hsn': hsn,
    #                 'product_id': vals['product_id'],
    #                 'family_rec': vals['family_rec'],
    #                 'category_rec': vals['category_rec'],
    #                 'class_rec': vals['class_rec'],
    #                 'brick_rec': vals['brick_rec'],
    #                 'nhcl_tax': tax_name,
    #                 'nhcl_order_quantity': vals['qty'],
    #                 # 'nhcl_amount_total': vals['total'],
    #                 'nhcl_amount_total': float_round(vals['total'], precision_digits=0),
    #                 'nhcl_taxable_amount': vals['taxable'],
    #                 'nhcl_tax_amount': vals['tax'],
    #                 'nhcl_cgst_amount': vals['cgst'],
    #                 'nhcl_sgst_amount': vals['sgst'],
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'nhcl_pos_hsn_tax_id': self.id
    #             })
    #
    #         if vals_list:
    #             self.env['nhcl.hsn.tax.report.line'].create(vals_list)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'HSN TAX Report Lines',
    #         'res_model': 'nhcl.hsn.tax.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_pos_hsn_tax_id', '=', self.id)],
    #         'context': {
    #             'default_nhcl_pos_hsn_tax_id': self.id
    #         }
    #     }


    #############below
    # def get_hsn_with_tax_wise_report(self):
    #     self.nhcl_pos_hsn_tax_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         domain = [
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #             ('order_id.company_id', '=', store.nhcl_company_id.id),
    #             ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
    #         ]
    #
    #         # Filter by HSN code
    #         if self.l10n_in_hsn_code:
    #             domain.append((
    #                 'product_id.l10n_in_hsn_code',
    #                 '=',
    #                 self.l10n_in_hsn_code
    #             ))
    #
    #         # Filter by Tax
    #         if self.tax_id:
    #             domain.append((
    #                 'tax_ids',
    #                 'in',
    #                 self.tax_id.id
    #             ))
    #
    #         # ---------------------------------------------------------
    #         # FETCH POS ORDER LINES
    #         # ---------------------------------------------------------
    #
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         # ---------------------------------------------------------
    #         # TOTAL PRICE SUBTOTAL INCL
    #         # ---------------------------------------------------------
    #
    #         total_price_subtotal_incl = sum(
    #             pos_lines.mapped('price_subtotal_incl')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # TOTAL AMOUNT PAID
    #         # ---------------------------------------------------------
    #
    #         orders = pos_lines.mapped('order_id')
    #
    #         total_amount_paid = sum(
    #             orders.mapped('amount_paid')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING DIFFERENCE
    #         # ---------------------------------------------------------
    #
    #         rounding_amount = (
    #                 total_amount_paid - total_price_subtotal_incl
    #         )
    #
    #         # ---------------------------------------------------------
    #         # GROUPING
    #         # ---------------------------------------------------------
    #
    #         grouped_data = {}
    #
    #         for line in pos_lines:
    #
    #             product = line.product_id
    #
    #             if not product:
    #                 continue
    #
    #             categ = product.categ_id
    #
    #             family = ''
    #             category_name = ''
    #             class_name = ''
    #             brick_name = ''
    #
    #             if categ:
    #
    #                 parent_ids = [
    #                     int(x)
    #                     for x in (categ.parent_path or '')
    #                     .rstrip('/')
    #                     .split('/')
    #                     if x
    #                 ]
    #
    #                 # 1st level → Family
    #                 if len(parent_ids) >= 1:
    #                     family_rec = self.env[
    #                         'product.category'
    #                     ].browse(parent_ids[0])
    #
    #                     family = family_rec.name or ''
    #
    #                 # 2nd level → Category
    #                 if len(parent_ids) >= 2:
    #                     category_rec = self.env[
    #                         'product.category'
    #                     ].browse(parent_ids[1])
    #
    #                     category_name = category_rec.name or ''
    #
    #                 # 3rd level → Class
    #                 if len(parent_ids) >= 3:
    #                     class_rec = self.env[
    #                         'product.category'
    #                     ].browse(parent_ids[2])
    #
    #                     class_name = class_rec.name or ''
    #
    #                 # 4th level → Brick
    #                 if len(parent_ids) >= 4:
    #                     brick_rec = self.env[
    #                         'product.category'
    #                     ].browse(parent_ids[3])
    #
    #                     brick_name = brick_rec.name or ''
    #
    #             hsn_code = product.l10n_in_hsn_code or 'N/A'
    #
    #             tax = line.tax_ids[:1]
    #             tax_name = tax.name if tax else 'No Tax'
    #
    #             qty = line.qty
    #             subtotal = line.price_subtotal
    #             subtotal_incl = line.price_subtotal_incl
    #
    #             tax_amount = subtotal_incl - subtotal
    #
    #             key = (
    #                 store.id,
    #                 hsn_code,
    #                 tax_name,
    #                 product.id
    #             )
    #
    #             if key not in grouped_data:
    #                 grouped_data[key] = {
    #                     'family_rec': family,
    #                     'category_rec': category_name,
    #                     'class_rec': class_name,
    #                     'brick_rec': brick_name,
    #
    #                     'product_id': product.id,
    #
    #                     # All product types quantity
    #                     'qty': 0.0,
    #
    #                     # Only storable/product quantity
    #                     'storable_qty': 0.0,
    #
    #                     'taxable': 0.0,
    #                     'total': 0.0,
    #                     'tax': 0.0,
    #                     'cgst': 0.0,
    #                     'sgst': 0.0,
    #                 }
    #
    #             # -----------------------------------------------------
    #             # ALL TYPES QUANTITY
    #             # -----------------------------------------------------
    #
    #             grouped_data[key]['qty'] += qty
    #
    #             # -----------------------------------------------------
    #             # ONLY STORABLE PRODUCT QUANTITY
    #             # detailed_type == 'product'
    #             # -----------------------------------------------------
    #
    #             if product.detailed_type == 'product':
    #                 grouped_data[key]['storable_qty'] += qty
    #
    #             # -----------------------------------------------------
    #             # AMOUNTS
    #             # -----------------------------------------------------
    #
    #             grouped_data[key]['taxable'] += subtotal
    #
    #             grouped_data[key]['total'] += subtotal_incl
    #
    #             grouped_data[key]['tax'] += tax_amount
    #
    #             grouped_data[key]['cgst'] += tax_amount / 2
    #
    #             grouped_data[key]['sgst'] += tax_amount / 2
    #
    #         # ---------------------------------------------------------
    #         # CREATE NORMAL REPORT LINES
    #         # ---------------------------------------------------------
    #
    #         vals_list = []
    #
    #         for (
    #                 store_id,
    #                 hsn,
    #                 tax_name,
    #                 product_id
    #         ), vals in grouped_data.items():
    #             vals_list.append({
    #
    #                 'nhcl_hsn': hsn,
    #
    #                 'product_id': vals['product_id'],
    #
    #                 'family_rec': vals['family_rec'],
    #                 'category_rec': vals['category_rec'],
    #                 'class_rec': vals['class_rec'],
    #                 'brick_rec': vals['brick_rec'],
    #
    #                 'nhcl_tax': tax_name,
    #
    #                 # All types quantity
    #                 'nhcl_order_quantity': vals['qty'],
    #
    #                 # Only storable quantity
    #                 'storable_qty': vals['storable_qty'],
    #
    #                 # Existing amount calculation - unchanged
    #                 'nhcl_amount_total': vals['total'],
    #
    #                 'nhcl_taxable_amount': vals['taxable'],
    #
    #                 'nhcl_tax_amount': vals['tax'],
    #
    #                 'nhcl_cgst_amount': vals['cgst'],
    #
    #                 'nhcl_sgst_amount': vals['sgst'],
    #
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #
    #                 # From / To Date
    #                 'from_date': store.from_date,
    #                 'to_date': store.to_date,
    #
    #                 'nhcl_pos_hsn_tax_id': self.id,
    #             })
    #
    #         if vals_list:
    #             self.env[
    #                 'nhcl.hsn.tax.report.line'
    #             ].create(vals_list)
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING UP LINE - LAST
    #         # ---------------------------------------------------------
    #
    #         if rounding_amount != 0:
    #
    #             rounding_product = self.env[
    #                 'product.product'
    #             ].search([
    #                 ('name', '=', 'Rounding Up')
    #             ], limit=1)
    #
    #             if not rounding_product:
    #                 raise ValidationError(
    #                     "Rounding Up product is not available in Products."
    #                 )
    #
    #             self.env[
    #                 'nhcl.hsn.tax.report.line'
    #             ].create({
    #
    #                 'nhcl_hsn': 'N/A',
    #
    #                 # Rounding Up product
    #                 'product_id': rounding_product.id,
    #
    #                 'family_rec': '',
    #                 'category_rec': '',
    #                 'class_rec': '',
    #                 'brick_rec': 'Rounding Up',
    #
    #                 'nhcl_tax': 'No Tax',
    #
    #                 'nhcl_order_quantity': 0.0,
    #
    #                 'storable_qty': 0.0,
    #
    #                 # ONLY rounding difference
    #                 'nhcl_amount_total': rounding_amount,
    #
    #                 # Don't add rounding to tax values
    #                 'nhcl_taxable_amount': 0.0,
    #                 'nhcl_tax_amount': 0.0,
    #                 'nhcl_cgst_amount': 0.0,
    #                 'nhcl_sgst_amount': 0.0,
    #
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #
    #                 # From / To Date
    #                 'from_date': store.from_date,
    #                 'to_date': store.to_date,
    #
    #                 'nhcl_pos_hsn_tax_id': self.id,
    #             })
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'HSN TAX Report Lines',
    #         'res_model': 'nhcl.hsn.tax.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [
    #             ('nhcl_pos_hsn_tax_id', '=', self.id)
    #         ],
    #         'context': {
    #             'default_nhcl_pos_hsn_tax_id': self.id
    #         }
    #     }

    def get_hsn_with_tax_wise_report(self):
        self.nhcl_pos_hsn_tax_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
            ]

            # ---------------------------------------------------------
            # FILTER BY HSN CODE
            # ---------------------------------------------------------

            if self.l10n_in_hsn_code:
                domain.append((
                    'product_id.l10n_in_hsn_code',
                    '=',
                    self.l10n_in_hsn_code
                ))

            # ---------------------------------------------------------
            # FILTER BY TAX
            # ---------------------------------------------------------

            if self.tax_id:
                domain.append((
                    'tax_ids',
                    'in',
                    self.tax_id.id
                ))

            # ---------------------------------------------------------
            # FETCH POS LINES
            # ---------------------------------------------------------

            pos_lines = self.env['pos.order.line'].search(domain)

            grouped_data = {}

            # ---------------------------------------------------------
            # NORMAL POS LINES
            # ---------------------------------------------------------

            for line in pos_lines:

                product = line.product_id

                if not product:
                    continue

                categ = product.categ_id

                family = ''
                category_name = ''
                class_name = ''
                brick_name = ''

                if categ:

                    parent_ids = [
                        int(x)
                        for x in
                        (categ.parent_path or '').rstrip('/').split('/')
                        if x
                    ]

                    # 1st level -> Family
                    if len(parent_ids) >= 1:
                        family_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[0])

                        family = family_rec.name or ''

                    # 2nd level -> Category
                    if len(parent_ids) >= 2:
                        category_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[1])

                        category_name = category_rec.name or ''

                    # 3rd level -> Class
                    if len(parent_ids) >= 3:
                        class_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[2])

                        class_name = class_rec.name or ''

                    # 4th level -> Brick
                    if len(parent_ids) >= 4:
                        brick_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[3])

                        brick_name = brick_rec.name or ''

                # -----------------------------------------------------
                # HSN
                # -----------------------------------------------------

                hsn_code = product.l10n_in_hsn_code or 'N/A'

                # -----------------------------------------------------
                # TAX
                # -----------------------------------------------------

                tax = line.tax_ids[:1]

                tax_name = tax.name if tax else 'No Tax'

                # -----------------------------------------------------
                # VALUES
                # -----------------------------------------------------

                qty = line.qty

                subtotal = line.price_subtotal

                subtotal_incl = line.price_subtotal_incl

                tax_amount = subtotal_incl - subtotal

                # -----------------------------------------------------
                # STORABLE QTY
                # -----------------------------------------------------

                storable_qty = 0.0

                if product.detailed_type == 'product':
                    storable_qty = qty

                # -----------------------------------------------------
                # GROUP KEY
                # -----------------------------------------------------

                key = (
                    store.id,
                    hsn_code,
                    tax_name,
                    product.id
                )

                if key not in grouped_data:
                    grouped_data[key] = {
                        'family_rec': family,
                        'category_rec': category_name,
                        'class_rec': class_name,
                        'brick_rec': brick_name,

                        'product_id': product.id,

                        'qty': 0.0,
                        'storable_qty': 0.0,

                        'taxable': 0.0,
                        'total': 0.0,
                        'tax': 0.0,
                        'cgst': 0.0,
                        'sgst': 0.0,
                    }

                # -----------------------------------------------------
                # QUANTITY
                # -----------------------------------------------------

                grouped_data[key]['qty'] += qty

                # -----------------------------------------------------
                # STORABLE QUANTITY
                # -----------------------------------------------------

                grouped_data[key]['storable_qty'] += storable_qty

                # -----------------------------------------------------
                # AMOUNTS
                # -----------------------------------------------------

                grouped_data[key]['taxable'] += subtotal

                grouped_data[key]['total'] += subtotal_incl

                grouped_data[key]['tax'] += tax_amount

                grouped_data[key]['cgst'] += tax_amount / 2

                grouped_data[key]['sgst'] += tax_amount / 2

            # ---------------------------------------------------------
            # CREATE NORMAL REPORT LINES
            # ---------------------------------------------------------

            vals_list = []

            for (
                    store_id,
                    hsn,
                    tax_name,
                    product_id
            ), vals in grouped_data.items():
                vals_list.append({

                    'nhcl_hsn': hsn,

                    'product_id': vals['product_id'],

                    'family_rec': vals['family_rec'],

                    'category_rec': vals['category_rec'],

                    'class_rec': vals['class_rec'],

                    'brick_rec': vals['brick_rec'],

                    'nhcl_tax': tax_name,

                    'nhcl_order_quantity': vals['qty'],

                    'storable_qty': vals['storable_qty'],

                    'nhcl_amount_total': vals['total'],

                    'nhcl_taxable_amount': vals['taxable'],

                    'nhcl_tax_amount': vals['tax'],

                    'nhcl_cgst_amount': vals['cgst'],

                    'nhcl_sgst_amount': vals['sgst'],

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'from_date': store.from_date,

                    'to_date': store.to_date,

                    'nhcl_pos_hsn_tax_id': self.id,
                })

            # ---------------------------------------------------------
            # POS EXCHANGE
            # ---------------------------------------------------------

            exchange_moves = self.env['stock.move'].search([
                ('date', '>=', from_date),
                ('date', '<=', to_date),
                ('state', '=', 'done'),
                ('nhcl_exchange', '=', True),
                ('company_id', '=', store.nhcl_company_id.id),
            ])

            for move in exchange_moves:

                product = move.product_id

                if not product:
                    continue

                # -----------------------------------------------------
                # ONLY STORABLE PRODUCTS
                # -----------------------------------------------------

                if product.detailed_type != 'product':
                    continue

                # -----------------------------------------------------
                # CATEGORY HIERARCHY
                # Same as normal POS
                # -----------------------------------------------------

                categ = product.categ_id

                family = ''
                category_name = ''
                class_name = ''
                brick_name = ''

                if categ:

                    parent_ids = [
                        int(x)
                        for x in
                        (categ.parent_path or '').rstrip('/').split('/')
                        if x
                    ]

                    # 1st level -> Family
                    if len(parent_ids) >= 1:
                        family_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[0])

                        family = family_rec.name or ''

                    # 2nd level -> Category
                    if len(parent_ids) >= 2:
                        category_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[1])

                        category_name = category_rec.name or ''

                    # 3rd level -> Class
                    if len(parent_ids) >= 3:
                        class_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[2])

                        class_name = class_rec.name or ''

                    # 4th level -> Brick
                    if len(parent_ids) >= 4:
                        brick_rec = self.env[
                            'product.category'
                        ].browse(parent_ids[3])

                        brick_name = brick_rec.name or ''

                # -----------------------------------------------------
                # HSN
                # stock.move -> lot_ids -> stock.lot
                # -----------------------------------------------------

                hsn_code = 'N/A'

                lot = move.lot_ids[:1]

                if lot:
                    hsn_code = lot.nhcl_lot_hsn_code or 'N/A'

                # -----------------------------------------------------
                # TAX
                # stock.move -> nhcl_tax_ids
                # -----------------------------------------------------

                tax = move.nhcl_tax_ids[:1]

                tax_name = tax.name if tax else 'No Tax'

                # -----------------------------------------------------
                # EXCHANGE VALUES
                # NEGATIVE
                # -----------------------------------------------------

                exchange_qty = -(move.quantity or 0.0)

                exchange_taxable = -(
                        move.nhcl_price_subtotal or 0.0
                )

                exchange_total = -(
                        move.nhcl_price_total or 0.0
                )

                # -----------------------------------------------------
                # TAX AMOUNT
                # -----------------------------------------------------

                exchange_tax_amount = (
                        exchange_total - exchange_taxable
                )

                # -----------------------------------------------------
                # CGST / SGST
                # -----------------------------------------------------

                exchange_cgst = exchange_tax_amount / 2

                exchange_sgst = exchange_tax_amount / 2

                # -----------------------------------------------------
                # EXCHANGE AS SEPARATE LINE
                # -----------------------------------------------------

                vals_list.append({

                    'nhcl_hsn': hsn_code,

                    'product_id': product.id,

                    # Exchange product category details
                    'family_rec': family,
                    'category_rec': category_name,
                    'class_rec': class_name,
                    'brick_rec': brick_name,

                    'nhcl_tax': tax_name,

                    # Negative exchange quantity
                    'nhcl_order_quantity': exchange_qty,

                    'storable_qty': exchange_qty,

                    # Negative amounts
                    'nhcl_amount_total': exchange_total,

                    'nhcl_taxable_amount': exchange_taxable,

                    'nhcl_tax_amount': exchange_tax_amount,

                    'nhcl_cgst_amount': exchange_cgst,

                    'nhcl_sgst_amount': exchange_sgst,

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'from_date': store.from_date,

                    'to_date': store.to_date,

                    'nhcl_pos_hsn_tax_id': self.id,
                })

            # ---------------------------------------------------------
            # CREATE NORMAL + EXCHANGE LINES
            # ---------------------------------------------------------

            if vals_list:
                self.env[
                    'nhcl.hsn.tax.report.line'
                ].create(vals_list)

        # -------------------------------------------------------------
        # OPEN REPORT
        # -------------------------------------------------------------

        return {
            'type': 'ir.actions.act_window',
            'name': 'HSN TAX Report Lines',
            'res_model': 'nhcl.hsn.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                ('nhcl_pos_hsn_tax_id', '=', self.id)
            ],
            'context': {
                'default_nhcl_pos_hsn_tax_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_pos_hsn_tax_ids.unlink()


    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['HSN', 'TAX%', 'BILLQTY', 'NETAMT', 'TAXABLEAMT', 'CGSTAMT', 'SGSTAMT']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_hsn_tax_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_hsn)
            worksheet.write(row_num, 1, line.nhcl_tax)
            worksheet.write(row_num, 2, line.nhcl_order_quantity)
            worksheet.write(row_num, 3, line.nhcl_amount_total)
            worksheet.write(row_num, 4, line.nhcl_taxable_amount)
            worksheet.write(row_num, 5, line.nhcl_cgst_amount)
            worksheet.write(row_num, 6, line.nhcl_sgst_amount)

        # Close the workbook
        workbook.close()

        # Get the content of the buffer
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # Encode the data in base64
        encoded_data = base64.b64encode(excel_data)

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'POS_HSN_Wise_Tax_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_HSN_Wise_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_hsn_tax_lines(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'HSN TAX Report Lines',
            'res_model': 'nhcl.hsn.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hsn_tax_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hsn_tax_id': self.id
            }
        }


class NhclHSNTaxReportLine(models.Model):
    _name = 'nhcl.hsn.tax.report.line'
    _description = "hsn tax report"

    nhcl_pos_hsn_tax_id = fields.Many2one('nhcl.hsn.tax.report', string="HSN Tax Report")
    nhcl_hsn = fields.Char(string="HSN")
    product_id = fields.Many2one(
        'product.product',
        string="Product"
    )
    nhcl_tax = fields.Char(string="Tax%")
    family_rec = fields.Char(string="Family")
    category_rec = fields.Char(string="Category")
    class_rec = fields.Char(string="Class")
    brick_rec = fields.Char(string="Brick")
    nhcl_order_quantity = fields.Float(string="Qty(service prdct)", digits='Product Unit of Measure')
    nhcl_amount_total = fields.Float(string="Amount Total(Tax Incl)")
    nhcl_taxable_amount = fields.Float(string="Amount Total(Tax Excl)")
    nhcl_tax_amount = fields.Float(string="TAX AMT")
    nhcl_cgst_amount = fields.Float(string="CGST AMT")
    nhcl_sgst_amount = fields.Float(string="SGST AMT")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    from_date = fields.Datetime(
        string="From Date"
    )

    to_date = fields.Datetime(
        string="To Date"
    )

    storable_qty = fields.Float(
        string="Quantity",
        digits='Product Unit of Measure'
    )