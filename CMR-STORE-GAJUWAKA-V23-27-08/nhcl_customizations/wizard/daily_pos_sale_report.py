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


class NhclDailySaleReport(models.Model):
    _name = 'nhcl.daily.sale.report'
    _description = "Daily Sale Report"
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
    nhcl_daily_sale_report_ids = fields.One2many('nhcl.daily.sale.report.line', 'nhcl_daily_sale_report_id')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    name = fields.Char(string='Name', default='Daily Sale DSD Report')
    total_bill_qty = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qty')
    total_net_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Amount')
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

    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.nhcl_class = False
        self.brick = False

    @api.onchange('category')
    def _onchange_category(self):
        self.nhcl_class = False
        self.brick = False

    @api.onchange('nhcl_class')
    def _onchange_nhcl_class(self):
        self.brick = False

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_daily_sale_report_ids
            rec.total_bill_qty = sum(lines.mapped('bill_qty'))
            rec.total_net_amount = sum(lines.mapped('net_amount'))

    #11-05-2026
    # def daily_sale_dsd_report(self):
    #     self.nhcl_daily_sale_report_ids.unlink()
    #
    #     user_tz = self.env.user.tz or 'UTC'
    #     local = pytz.timezone(user_tz)
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         domain = [
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #             ('order_id.company_id', '=', store.nhcl_company_id.id)
    #         ]
    #
    #         # Apply product category filters
    #         if store.family:
    #             domain.append(
    #                 ('product_id.categ_id.parent_id.parent_id.parent_id', '=', store.family.id)
    #             )
    #
    #         if store.category:
    #             domain.append(
    #                 ('product_id.categ_id.parent_id.parent_id', '=', store.category.id)
    #             )
    #
    #         if store.nhcl_class:
    #             domain.append(
    #                 ('product_id.categ_id.parent_id', '=', store.nhcl_class.id)
    #             )
    #
    #         if store.brick:
    #             domain.append(
    #                 ('product_id.categ_id', '=', store.brick.id)
    #             )
    #
    #         # Search filtered POS Order Lines
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         for line in pos_lines:
    #             product = line.product_id
    #             barcode = product.barcode
    #
    #             if not barcode:
    #                 continue
    #
    #             categ = product.categ_id
    #
    #             family = (
    #                 categ.parent_id.parent_id.parent_id.complete_name
    #                 if categ.parent_id and categ.parent_id.parent_id and categ.parent_id.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             category = (
    #                 categ.parent_id.parent_id.complete_name
    #                 if categ.parent_id and categ.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             class_name = (
    #                 categ.parent_id.complete_name
    #                 if categ.parent_id
    #                 else ''
    #             )
    #
    #             brick = categ.complete_name
    #
    #             existing_line = self.nhcl_daily_sale_report_ids.filtered(
    #                 lambda x:
    #                 x.nhcl_company_id.id == store.nhcl_company_id.id and
    #                 x.family_name == family and
    #                 x.category_name == category and
    #                 x.class_name == class_name and
    #                 x.brick_name == brick
    #             )
    #
    #             if existing_line:
    #                 existing_line.write({
    #                     'bill_qty': existing_line.bill_qty + line.qty,
    #                     'net_amount': existing_line.net_amount + line.price_subtotal_incl,
    #                 })
    #             else:
    #                 self.env['nhcl.daily.sale.report.line'].create({
    #                     'family_name': family,
    #                     'category_name': category,
    #                     'class_name': class_name,
    #                     'brick_name': brick,
    #                     'bill_qty': line.qty,
    #                     'net_amount': line.price_subtotal_incl,
    #                     'nhcl_company_id': store.nhcl_company_id.id,
    #                     'config_id': line.order_id.config_id.id,
    #                     'nhcl_daily_sale_report_id': self.id
    #                 })
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Daily sale DSD Report',
    #         'res_model': 'nhcl.daily.sale.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_daily_sale_report_id', '=', self.id)],
    #         'context': {
    #             'default_read_group': self.id
    #         }
    #     }

    def daily_sale_dsd_report(self):
        self.nhcl_daily_sale_report_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:
            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),

            ]

            # Category filters
            if store.family:
                domain.append(
                    ('product_id.categ_id.parent_id.parent_id.parent_id', '=', store.family.id)
                )
            if store.category:
                domain.append(
                    ('product_id.categ_id.parent_id.parent_id', '=', store.category.id)
                )
            if store.nhcl_class:
                domain.append(
                    ('product_id.categ_id.parent_id', '=', store.nhcl_class.id)
                )
            if store.brick:
                domain.append(
                    ('product_id.categ_id', '=', store.brick.id)
                )

            pos_lines = self.env['pos.order.line'].search(domain)

            #  CACHE category hierarchy (very important)
            categ_cache = {}

            def get_categ_names(categ):
                if categ.id in categ_cache:
                    return categ_cache[categ.id]

                family = (
                    categ.parent_id.parent_id.parent_id.complete_name
                    if categ.parent_id and categ.parent_id.parent_id and categ.parent_id.parent_id.parent_id
                    else ''
                )
                category = (
                    categ.parent_id.parent_id.complete_name
                    if categ.parent_id and categ.parent_id.parent_id
                    else ''
                )
                class_name = (
                    categ.parent_id.complete_name
                    if categ.parent_id else ''
                )
                brick = categ.complete_name

                categ_cache[categ.id] = (family, category, class_name, brick)
                return categ_cache[categ.id]

            #  Python dictionary grouping (replaces filtered + write)
            grouped = {}

            for line in pos_lines:
                product = line.product_id
                barcode = product.barcode
                if not barcode:
                    continue
                categ = product.categ_id
                family, category, class_name, brick = get_categ_names(categ)

                key = (
                    store.nhcl_company_id.id,
                    family,
                    category,
                    class_name,
                    brick,
                )

                if key not in grouped:
                    grouped[key] = {
                        'family_name': family,
                        'category_name': category,
                        'class_name': class_name,
                        'brick_name': brick,
                        'bill_qty': 0.0,
                        'net_amount': 0.0,
                        'nhcl_company_id': store.nhcl_company_id.id,
                        'config_id': line.order_id.config_id.id,
                        'nhcl_daily_sale_report_id': self.id,
                    }

                grouped[key]['bill_qty'] += line.qty
                grouped[key]['net_amount'] += line.price_subtotal_incl

            # Bulk create (single query)
            self.env['nhcl.daily.sale.report.line'].create(list(grouped.values()))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily sale DSD Report',
            'res_model': 'nhcl.daily.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_report_id', '=', self.id)],
        }


    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_daily_sale_report_ids.unlink()


    def action_daily_sale_detailed_view(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily sale DSD Report',
            'res_model': 'nhcl.daily.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_report_id', '=', self.id)],
            'context': {
                'default_read_group': self.id
            }
        }

class NhclDailySaleReportLine(models.Model):
    _name = 'nhcl.daily.sale.report.line'
    _description = "nhcl daily sale report line"

    nhcl_daily_sale_report_id = fields.Many2one('nhcl.daily.sale.report', string="Daily Sale Report")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    bill_qty = fields.Float(string="BillQty")
    net_amount = fields.Float(string="Total Amount")
    config_id = fields.Many2one('pos.config', string='Terminal')
