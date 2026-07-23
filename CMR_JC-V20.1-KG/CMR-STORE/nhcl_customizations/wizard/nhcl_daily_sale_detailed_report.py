from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclDailySaleDetailedReport(models.Model):
    _name = 'nhcl.daily.sale.detailed.report'
    _description = "Daily Sale Detailed Report"
    _rec_name = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_daily_sale_detailed_report_ids = fields.One2many('nhcl.daily.sale.detailed.report.line', 'nhcl_daily_sale_detailed_report_id')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qty')
    total_mrp = fields.Float(compute="_compute_nhcl_show_totals", string='Total MRP')
    total_rsp_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total RSP')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    total_sale_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Sale')
    total_net_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Net')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    config_id = fields.Many2one('pos.config', string='Terminal')
    cashier_id = fields.Many2one('hr.employee', string='Cashier')
    family = fields.Many2one(
        'product.category',
        string='Family',
        domain=[('parent_id', '=', False)]
    )

    category = fields.Many2one(
        'product.category',
        string='Category',
        domain="[('parent_id', '=', family)]"
    )

    nhcl_class = fields.Many2one(
        'product.category',
        string='Class',
        domain="[('parent_id', '=', category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string='Brick',
        domain="[('parent_id', '=', nhcl_class)]"
    )
    aging = fields.Many2one('product.aging.line', string='Aging Code')
    brand = fields.Many2one('product.attribute.value', string='Brand', copy=False,
                                 domain=[('attribute_id.name', '=', 'Brand')])
    product_id = fields.Many2one('product.product', string='Product')
    unbrand_serial = fields.Many2one('stock.lot', string='Serial Number')
    branded_barcode = fields.Char(string="Brand Barcode")
    price_point = fields.Float(string="Price Point")
    name = fields.Char('Name', default="Article Wise Detailed Sale Report")
    # ----------------------------
    # Onchange methods
    # ----------------------------
    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.nhcl_class = False
        self.brick = False
        # self.product_id = False

    @api.onchange('category')
    def _onchange_category(self):
        self.nhcl_class = False
        self.brick = False
        # self.product_id = False

    @api.onchange('nhcl_class')
    def _onchange_nhcl_class(self):
        self.brick = False
        # self.product_id = False

    # @api.onchange('brick')
    # def _onchange_brick(self):
    #     self.product_id = False

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_daily_sale_detailed_report_ids
            rec.total_order_quantity = sum(lines.mapped('bill_qty'))
            rec.total_mrp = sum(lines.mapped('mrp'))
            rec.total_rsp_amount = sum(lines.mapped('rsp_amount'))
            rec.total_tax_amount = sum(lines.mapped('tax_amount'))
            rec.total_sale_amount = sum(lines.mapped('sale_amount'))
            rec.total_net_amount = sum(lines.mapped('net_amount'))
            rec.total_discount_amount = sum(lines.mapped('discount'))


    def daily_sale_detailed_report(self):
        self.nhcl_daily_sale_detailed_report_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:
            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),
                ('order_id.state', '=', 'invoiced'),
                ('product_id.detailed_type', '=', 'product'),
                ('order_id.refunded_orders_count', '=', 0)
            ]

            if store.config_id:
                domain.append(
                    ('order_id.config_id', '=', store.config_id.id)
                )

            if store.cashier_id:
                domain.append(
                    ('order_id.employee_id', '=', store.cashier_id.id)
                )

            if store.brick:
                domain.append(
                    ('product_id.categ_id', '=', store.brick.id)
                )

            if store.product_id:
                domain.append(
                    ('product_id', '=', store.product_id.id)
                )

            pos_lines = self.env['pos.order.line'].search(domain)

            report_vals = []
            lot_cache = {}

            for line in pos_lines:
                product = line.product_id
                categ = product.categ_id

                # -------------------------
                # Price Point Line-wise Filter
                # -------------------------
                if store.price_point and line.price_unit != store.price_point:
                    continue

                serial_id = False

                if line.pack_lot_ids:
                    lot_name = line.pack_lot_ids[0].display_name

                    if lot_name:
                        if lot_name not in lot_cache:
                            lot_cache[lot_name] = self.env['stock.lot'].search(
                                [('name', '=', lot_name)],
                                limit=1
                            )

                        serial_id = lot_cache[lot_name]

                family = ''
                category_name = ''
                class_name = ''
                brick_name = ''

                family_rec = False
                category_rec = False
                class_rec = False

                if categ:
                    brick_name = categ.complete_name or ''

                    if categ.parent_id:
                        class_name = categ.parent_id.complete_name or ''
                        class_rec = categ.parent_id

                        if categ.parent_id.parent_id:
                            category_name = (
                                    categ.parent_id.parent_id.complete_name or ''
                            )
                            category_rec = categ.parent_id.parent_id

                            if categ.parent_id.parent_id.parent_id:
                                family = (
                                        categ.parent_id.parent_id.parent_id.complete_name or ''
                                )
                                family_rec = (
                                    categ.parent_id.parent_id.parent_id
                                )

                # Family filter
                if store.family and family_rec != store.family:
                    continue

                # Category filter
                if store.category and category_rec != store.category:
                    continue

                # Class filter
                if store.nhcl_class and class_rec != store.nhcl_class:
                    continue

                # Aging filter
                if store.aging:
                    if not serial_id or serial_id.description_1 != store.aging:
                        continue

                # Unbrand Serial filter
                if store.unbrand_serial:
                    if not serial_id or serial_id != store.unbrand_serial:
                        continue

                # Branded Barcode filter
                if store.branded_barcode:
                    if not serial_id or serial_id.ref != store.branded_barcode:
                        continue

                # Brand filter
                if store.brand:
                    if not serial_id or serial_id.category_3 != store.brand:
                        continue

                report_vals.append({
                    'family_name': family,
                    'category_name': category_name,
                    'class_name': class_name,
                    'brick_name': brick_name,
                    'product_name': product.name,
                    'hsn': product.l10n_in_hsn_code or '',
                    'uom': product.uom_id.name or '',
                    'promo': line.nhcl_reward_id.display_name,
                    'customer_note': line.order_id.note,

                    'colour': serial_id.category_1.name if serial_id and serial_id.category_1 else '',
                    'aging': serial_id.description_1.name if serial_id and serial_id.description_1 else '',
                    'fit': serial_id.category_2.name if serial_id and serial_id.category_2 else '',
                    'design': serial_id.category_8.name if serial_id and serial_id.category_8 else '',
                    'brand': serial_id.category_3.name if serial_id and serial_id.category_3 else '',
                    'size': serial_id.category_7.name if serial_id and serial_id.category_7 else '',
                    'barcode': serial_id.ref if serial_id else '',
                    'serial': serial_id.name if serial_id else '',

                    'bill_qty': line.qty,
                    'mrp': line.nhcl_mr_price,
                    'rsp_amount': line.price_unit,

                    'tax_persent': ', '.join(
                        line.tax_ids_after_fiscal_position.mapped('name')
                    ) if line.tax_ids_after_fiscal_position else '',

                    'tax_amount': line.price_subtotal_incl - line.price_subtotal,
                    'sale_amount': line.price_subtotal_incl,
                    'net_amount': line.price_subtotal_incl,
                    'discount': line.order_id.amount_discount,

                    'config_id': line.order_id.config_id.id,
                    'cashier_id': line.order_id.employee_id.id,
                    'nhcl_bill_receipt': line.order_id.pos_reference,
                    'nhcl_date_order': line.order_id.date_order,
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'nhcl_daily_sale_detailed_report_id': self.id
                })

            if report_vals:
                self.env[
                    'nhcl.daily.sale.detailed.report.line'
                ].create(report_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Sale Detailed Report',
            'res_model': 'nhcl.daily.sale.detailed.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_detailed_report_id', '=', self.id)],
            'context': {
                'default_nhcl_daily_sale_detailed_report_id': self.id
            }
        }

    def action_view_detailed_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Sale Detailed Report',
            'res_model': 'nhcl.daily.sale.detailed.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_detailed_report_id', '=', self.id)],
            'context': {
                'default_nhcl_daily_sale_detailed_report_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False,
            'family': False,
            'category': False,
            'nhcl_class': False,
            'brick': False,
            'product_id': False,
            'price_point': False,
            'config_id': False,
            'cashier_id': False,
            'aging': False,
            'brand': False,
        })
        self.nhcl_daily_sale_detailed_report_ids.unlink()

class NhclDailySaleDetailedReportLine(models.Model):
    _name = 'nhcl.daily.sale.detailed.report.line'
    _description = "nhcl daily sale detailed report line"

    nhcl_daily_sale_detailed_report_id = fields.Many2one('nhcl.daily.sale.detailed.report', string="Daily Sale Report")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    config_id = fields.Many2one('pos.config', string='Terminal')
    cashier_id = fields.Many2one('hr.employee', string='Cashier')
    nhcl_bill_receipt = fields.Char(string="Bill Receipt")
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    product_name = fields.Char(string="Product")
    hsn = fields.Char(string="HSN")
    colour = fields.Char(string="Colour")
    aging = fields.Char(string="Aging")
    fit = fields.Char(string="Fit")
    design = fields.Char(string="Design")
    size = fields.Char(string="Size")
    brand = fields.Char(string="Brand")
    barcode = fields.Char(string="Barcode")
    serial = fields.Char(string="Serial No")
    bill_qty = fields.Float(string="BillQty")
    mrp = fields.Float(string="MRP")
    tax_persent = fields.Char(string="Tax Persent")
    tax_amount = fields.Float(string="Tax Amount")
    sale_amount = fields.Float(string="Sale Value")
    rsp_amount = fields.Float(string="RSP")
    net_amount = fields.Float(string="Net Amt")
    nhcl_date_order = fields.Datetime(string="Date")
    uom = fields.Char(string="UOM")
    discount = fields.Float(string="Discount")
    promo = fields.Char(string="Promo")
    customer_note = fields.Char(string="Customer Note")