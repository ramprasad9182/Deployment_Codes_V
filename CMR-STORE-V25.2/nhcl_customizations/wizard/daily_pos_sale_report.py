from odoo import models,fields,api,_
import requests
from datetime import datetime, time, timedelta
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict
from odoo.exceptions import ValidationError


class NhclDailySaleReport(models.Model):
    _name = 'nhcl.daily.sale.report'
    _description = "Daily Sale Report"
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
    nhcl_daily_sale_report_ids = fields.One2many('nhcl.daily.sale.report.line', 'nhcl_daily_sale_report_id')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name', default=lambda self: self.env.company)
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



    # def daily_sale_dsd_report(self):
    #     self.nhcl_daily_sale_report_ids.unlink()
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
    #         # ---------------------------------------------------------
    #         # CATEGORY FILTERS
    #         # ---------------------------------------------------------
    #
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
    #         # ---------------------------------------------------------
    #         # FETCH POS ORDER LINES
    #         # ---------------------------------------------------------
    #
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         # ---------------------------------------------------------
    #         # GET RELATED ORDERS
    #         # ---------------------------------------------------------
    #
    #         orders = pos_lines.mapped('order_id')
    #
    #         # ---------------------------------------------------------
    #         # TOTAL FROM POS ORDER LINE
    #         # ---------------------------------------------------------
    #
    #         total_price_subtotal_incl = sum(
    #             pos_lines.mapped('price_subtotal_incl')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # TOTAL AMOUNT PAID FROM POS ORDER
    #         # ---------------------------------------------------------
    #
    #         amount_paid_total = sum(
    #             orders.mapped('amount_paid')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING DIFFERENCE
    #         # ---------------------------------------------------------
    #
    #         rounding_amount = (
    #                 amount_paid_total - total_price_subtotal_incl
    #         )
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING UP PRODUCT VALIDATION
    #         # ---------------------------------------------------------
    #
    #         rounding_product = self.env['product.product'].search([
    #             ('name', '=', 'Rounding Up')
    #         ], limit=1)
    #
    #         if not rounding_product:
    #             raise ValidationError(
    #                 "Rounding Up product is not available in Products."
    #             )
    #
    #         # ---------------------------------------------------------
    #         # CACHE CATEGORY HIERARCHY
    #         # ---------------------------------------------------------
    #
    #         categ_cache = {}
    #
    #         def get_categ_names(categ):
    #
    #             if not categ:
    #                 return '', '', '', ''
    #
    #             if categ.id in categ_cache:
    #                 return categ_cache[categ.id]
    #
    #             family = (
    #                 categ.parent_id.parent_id.parent_id.name
    #                 if categ.parent_id
    #                    and categ.parent_id.parent_id
    #                    and categ.parent_id.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             category = (
    #                 categ.parent_id.parent_id.name
    #                 if categ.parent_id
    #                    and categ.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             class_name = (
    #                 categ.parent_id.name
    #                 if categ.parent_id
    #                 else ''
    #             )
    #
    #             brick = categ.name
    #
    #             categ_cache[categ.id] = (
    #                 family,
    #                 category,
    #                 class_name,
    #                 brick,
    #             )
    #
    #             return categ_cache[categ.id]
    #
    #         # ---------------------------------------------------------
    #         # PRODUCT LINES FIRST
    #         # REMAINING TYPES LAST
    #         # ---------------------------------------------------------
    #
    #         product_lines = pos_lines.filtered(
    #             lambda line: line.product_id.detailed_type == 'product'
    #         )
    #
    #         remaining_lines = pos_lines.filtered(
    #             lambda line: line.product_id.detailed_type != 'product'
    #         )
    #
    #         ordered_lines = product_lines + remaining_lines
    #
    #         # ---------------------------------------------------------
    #         # GROUPING
    #         # ---------------------------------------------------------
    #
    #         grouped = {}
    #
    #         for line in ordered_lines:
    #
    #             product = line.product_id
    #             categ = product.categ_id
    #
    #             family, category, class_name, brick = get_categ_names(categ)
    #
    #             key = (
    #                 store.nhcl_company_id.id,
    #                 family,
    #                 category,
    #                 class_name,
    #                 brick,
    #             )
    #
    #             if key not in grouped:
    #                 grouped[key] = {
    #                     'family_name': family,
    #                     'category_name': category,
    #                     'class_name': class_name,
    #                     'brick_name': brick,
    #                     'bill_qty': 0.0,
    #                     'storable_qty': 0.0,
    #                     'net_amount': 0.0,
    #                     'nhcl_company_id': store.nhcl_company_id.id,
    #                     'from_date': store.from_date,
    #                     'to_date': store.to_date,
    #                     'config_id': line.order_id.config_id.id,
    #                     'nhcl_config_id': line.order_id.config_id.name,
    #                     'nhcl_daily_sale_report_id': self.id,
    #                 }
    #
    #             # -----------------------------------------------------
    #             # BILL QTY
    #             # ALL PRODUCT TYPES
    #             # -----------------------------------------------------
    #
    #             grouped[key]['bill_qty'] += line.qty
    #
    #             # -----------------------------------------------------
    #             # STORABLE QTY
    #             # ONLY detailed_type = product
    #             # -----------------------------------------------------
    #
    #             if product.detailed_type == 'product':
    #                 grouped[key]['storable_qty'] += line.qty
    #
    #             # -----------------------------------------------------
    #             # NET AMOUNT
    #             # -----------------------------------------------------
    #
    #             grouped[key]['net_amount'] += line.price_subtotal_incl
    #
    #         # ---------------------------------------------------------
    #         # CREATE NORMAL REPORT LINES
    #         # ---------------------------------------------------------
    #
    #         if grouped:
    #             self.env['nhcl.daily.sale.report.line'].create(
    #                 list(grouped.values())
    #             )
    #
    #         # ---------------------------------------------------------
    #         # CREATE ROUNDING UP LINE LAST
    #         # ---------------------------------------------------------
    #
    #         if rounding_amount != 0:
    #             self.env['nhcl.daily.sale.report.line'].create({
    #                 'family_name': '',
    #                 'category_name': '',
    #                 'class_name': '',
    #                 'brick_name': 'Rounding Up',
    #                 'bill_qty': 0.0,
    #                 'storable_qty': 0.0,
    #                 'net_amount': rounding_amount,
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'from_date': store.from_date,
    #                 'to_date': store.to_date,
    #                 'config_id': orders[-1].config_id.id if orders else False,
    #                 'nhcl_config_id': (
    #                     orders[-1].config_id.name
    #                     if orders
    #                     else ''
    #                 ),
    #                 'nhcl_daily_sale_report_id': self.id,
    #             })
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Daily sale DSD Report',
    #         'res_model': 'nhcl.daily.sale.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [
    #             ('nhcl_daily_sale_report_id', '=', self.id)
    #         ],
    #     }


    # latest
    # def daily_sale_dsd_report(self):
    #     self.nhcl_daily_sale_report_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         # ---------------------------------------------------------
    #         # POS ORDER LINE DOMAIN
    #         # ---------------------------------------------------------
    #
    #         domain = [
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #             ('order_id.company_id', '=', store.nhcl_company_id.id),
    #             ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
    #         ]
    #
    #         # ---------------------------------------------------------
    #         # CATEGORY FILTERS
    #         # ---------------------------------------------------------
    #
    #         if store.family:
    #             domain.append(
    #                 (
    #                     'product_id.categ_id.parent_id.parent_id.parent_id',
    #                     '=',
    #                     store.family.id
    #                 )
    #             )
    #
    #         if store.category:
    #             domain.append(
    #                 (
    #                     'product_id.categ_id.parent_id.parent_id',
    #                     '=',
    #                     store.category.id
    #                 )
    #             )
    #
    #         if store.nhcl_class:
    #             domain.append(
    #                 (
    #                     'product_id.categ_id.parent_id',
    #                     '=',
    #                     store.nhcl_class.id
    #                 )
    #             )
    #
    #         if store.brick:
    #             domain.append(
    #                 (
    #                     'product_id.categ_id',
    #                     '=',
    #                     store.brick.id
    #                 )
    #             )
    #
    #         # ---------------------------------------------------------
    #         # FETCH POS ORDER LINES
    #         # ---------------------------------------------------------
    #
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         # ---------------------------------------------------------
    #         # GET RELATED ORDERS
    #         # ---------------------------------------------------------
    #
    #         orders = pos_lines.mapped('order_id')
    #
    #         # ---------------------------------------------------------
    #         # TOTAL POS AMOUNT
    #         # Used only for ROUNDING UP
    #         # ---------------------------------------------------------
    #
    #         total_price_subtotal_incl = sum(
    #             pos_lines.mapped('price_subtotal_incl')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # TOTAL AMOUNT PAID
    #         # Used only for ROUNDING UP
    #         # ---------------------------------------------------------
    #
    #         amount_paid_total = sum(
    #             orders.mapped('amount_paid')
    #         )
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING DIFFERENCE
    #         # ---------------------------------------------------------
    #
    #         rounding_amount = (
    #                 amount_paid_total - total_price_subtotal_incl
    #         )
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING UP PRODUCT
    #         # ---------------------------------------------------------
    #
    #         rounding_product = self.env['product.product'].search([
    #             ('name', '=', 'Rounding Up')
    #         ], limit=1)
    #
    #         # ---------------------------------------------------------
    #         # CATEGORY CACHE
    #         # ---------------------------------------------------------
    #
    #         categ_cache = {}
    #
    #         def get_categ_names(categ):
    #
    #             if not categ:
    #                 return '', '', '', ''
    #
    #             if categ.id in categ_cache:
    #                 return categ_cache[categ.id]
    #
    #             family = (
    #                 categ.parent_id.parent_id.parent_id.name
    #                 if categ.parent_id
    #                    and categ.parent_id.parent_id
    #                    and categ.parent_id.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             category = (
    #                 categ.parent_id.parent_id.name
    #                 if categ.parent_id
    #                    and categ.parent_id.parent_id
    #                 else ''
    #             )
    #
    #             class_name = (
    #                 categ.parent_id.name
    #                 if categ.parent_id
    #                 else ''
    #             )
    #
    #             brick = categ.name or ''
    #
    #             categ_cache[categ.id] = (
    #                 family,
    #                 category,
    #                 class_name,
    #                 brick,
    #             )
    #
    #             return categ_cache[categ.id]
    #
    #         # ---------------------------------------------------------
    #         # GROUP NORMAL POS LINES
    #         # ---------------------------------------------------------
    #
    #         grouped = {}
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
    #             family, category, class_name, brick = (
    #                 get_categ_names(categ)
    #             )
    #
    #             key = (
    #                 store.nhcl_company_id.id,
    #                 family,
    #                 category,
    #                 class_name,
    #                 brick,
    #             )
    #
    #             if key not in grouped:
    #                 grouped[key] = {
    #                     'family_name': family,
    #                     'category_name': category,
    #                     'class_name': class_name,
    #                     'brick_name': brick,
    #
    #                     # ALL PRODUCT TYPES
    #                     'bill_qty': 0.0,
    #
    #                     # ONLY STORABLE
    #                     'storable_qty': 0.0,
    #
    #                     'net_amount': 0.0,
    #
    #                     'nhcl_company_id':
    #                         store.nhcl_company_id.id,
    #
    #                     'from_date':
    #                         store.from_date,
    #
    #                     'to_date':
    #                         store.to_date,
    #
    #                     'config_id':
    #                         line.order_id.config_id.id,
    #
    #                     'nhcl_config_id':
    #                         line.order_id.config_id.name,
    #
    #                     'nhcl_daily_sale_report_id':
    #                         self.id,
    #                 }
    #
    #             # -----------------------------------------------------
    #             # BILL QTY
    #             # IMPORTANT:
    #             # ALL TYPES
    #             # EXCHANGE WILL NEVER MODIFY THIS
    #             # -----------------------------------------------------
    #
    #             grouped[key]['bill_qty'] += line.qty
    #
    #             # -----------------------------------------------------
    #             # STORABLE QTY
    #             # ONLY detailed_type == product
    #             # -----------------------------------------------------
    #
    #             if product.detailed_type == 'product':
    #                 grouped[key]['storable_qty'] += line.qty
    #
    #             # -----------------------------------------------------
    #             # NET AMOUNT
    #             # Existing calculation
    #             # -----------------------------------------------------
    #
    #             grouped[key]['net_amount'] += (
    #                 line.price_subtotal_incl
    #             )
    #
    #         # ---------------------------------------------------------
    #         # EXCHANGE MOVES
    #         # ---------------------------------------------------------
    #
    #         exchange_domain = [
    #             ('picking_id.date_done', '>=', from_date),
    #             ('picking_id.date_done', '<=', to_date),
    #             ('picking_id.stock_picking_type', '=', 'exchange'),
    #             ('picking_id.state', '=', 'done'),
    #             ('nhcl_exchange', '=', True),
    #             ('company_id', '=', store.nhcl_company_id.id),
    #         ]
    #
    #         exchange_moves = self.env['stock.move'].search(
    #             exchange_domain
    #         )
    #
    #         # ---------------------------------------------------------
    #         # GROUP EXCHANGE BY
    #         # COMPANY + FAMILY + CATEGORY + CLASS + BRICK
    #         # ---------------------------------------------------------
    #
    #         exchange_grouped = {}
    #
    #         for move in exchange_moves:
    #
    #             product = move.product_id
    #
    #             if not product:
    #                 continue
    #
    #             categ = product.categ_id
    #
    #             family, category, class_name, brick = (
    #                 get_categ_names(categ)
    #             )
    #
    #             exchange_key = (
    #                 store.nhcl_company_id.id,
    #                 family,
    #                 category,
    #                 class_name,
    #                 brick,
    #             )
    #
    #             if exchange_key not in exchange_grouped:
    #                 exchange_grouped[exchange_key] = {
    #                     'family_name': family,
    #                     'category_name': category,
    #                     'class_name': class_name,
    #                     'brick_name': brick,
    #
    #                     'qty': 0.0,
    #                     'amount': 0.0,
    #                 }
    #
    #             # -----------------------------------------------------
    #             # EXCHANGE QTY
    #             # -----------------------------------------------------
    #
    #             exchange_grouped[exchange_key]['qty'] += (
    #                     move.quantity or 0.0
    #             )
    #
    #             # -----------------------------------------------------
    #             # EXCHANGE AMOUNT
    #             # -----------------------------------------------------
    #
    #             exchange_grouped[exchange_key]['amount'] += (
    #                     move.nhcl_price_total or 0.0
    #             )
    #
    #         # ---------------------------------------------------------
    #         # APPLY EXCHANGE
    #         #
    #         # IMPORTANT:
    #         # bill_qty is NOT touched.
    #         #
    #         # Only:
    #         #   storable_qty
    #         #   net_amount
    #         # ---------------------------------------------------------
    #
    #         for exchange_key, exchange_values in exchange_grouped.items():
    #
    #             exchange_qty = exchange_values['qty']
    #             exchange_amount = exchange_values['amount']
    #
    #             if exchange_key in grouped:
    #def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )
    #                 # -------------------------------------------------
    #                 # MATCH FOUND
    #                 # -------------------------------------------------
    #
    #                 grouped[exchange_key]['storable_qty'] -= (
    #                     exchange_qty
    #                 )
    #
    #                 grouped[exchange_key]['net_amount'] -= (
    #                     exchange_amount
    #                 )
    #
    #             else:
    #
    #                 # -------------------------------------------------
    #                 # NO MATCH
    #                 #
    #                 # Create new exchange-only line.
    #                 #
    #                 # bill_qty = 0
    #                 # storable_qty = negative
    #                 # net_amount = negative
    #                 # -------------------------------------------------
    #
    #                 grouped[exchange_key] = {
    #                     'family_name':
    #                         exchange_values['family_name'],
    #
    #                     'category_name':
    #                         exchange_values['category_name'],
    #
    #                     'class_name':
    #                         exchange_values['class_name'],
    #
    #                     'brick_name':
    #                         exchange_values['brick_name'],
    #
    #                     # DO NOT ADD EXCHANGE TO BILL QTY
    #                     'bill_qty': 0.0,
    #
    #                     # EXCHANGE IS NEGATIVE
    #                     'storable_qty':
    #                         -exchange_qty,
    #
    #                     # EXCHANGE AMOUNT IS NEGATIVE
    #                     'net_amount':
    #                         -exchange_amount,
    #
    #                     'nhcl_company_id':
    #                         store.nhcl_company_id.id,
    #
    #                     'from_date':
    #                         store.from_date,
    #
    #                     'to_date':
    #                         store.to_date,
    #
    #                     'config_id': False,
    #                     'nhcl_config_id': '',
    #
    #                     'nhcl_daily_sale_report_id':
    #                         self.id,
    #                 }
    #
    #         # ---------------------------------------------------------
    #         # DEBUG
    #         # ---------------------------------------------------------
    #
    #         normal_bill_qty = sum(
    #             line.qty for line in pos_lines
    #         )
    #
    #         normal_storable_qty = sum(
    #             line.qty
    #             for line in pos_lines
    #             if line.product_id
    #             and line.product_id.detailed_type == 'product'
    #         )
    #
    #         normal_amount = sum(
    #             line.price_subtotal_incl
    #             for line in pos_lines
    #         )
    #
    #         exchange_qty_total = sum(
    #             values['qty']
    #             for values in exchange_grouped.values()
    #         )
    #
    #         exchange_amount_total = sum(
    #             values['amount']
    #             for values in exchange_grouped.values()
    #         )
    #
    #         final_storable_qty = (
    #                 normal_storable_qty
    #                 - exchange_qty_total
    #         )
    #
    #         final_amount = (
    #                 normal_amount
    #                 - exchange_amount_total
    #         )
    #
    #         print(
    #             "\n"
    #             "=========================================================\n"
    #             "                 EXCHANGE SUMMARY\n"
    #             "=========================================================\n"
    #             "BILL QTY (NO EXCHANGE CHANGE) : %s\n"
    #             "STORABLE QTY WITHOUT EXCHANGE : %s\n"
    #             "EXCHANGE QTY                  : %s\n"
    #             "FINAL STORABLE QTY             : %s\n"
    #             "AMOUNT WITHOUT EXCHANGE        : %s\n"
    #             "EXCHANGE AMOUNT                : %s\n"
    #             "FINAL AMOUNT                   : %s\n"
    #             "=========================================================\n"
    #             "              END EXCHANGE DEBUG\n"
    #             "========================================================="
    #             % (
    #                 normal_bill_qty,
    #                 normal_storable_qty,
    #                 exchange_qty_total,
    #                 final_storable_qty,
    #                 normal_amount,
    #                 exchange_amount_total,
    #                 final_amount,
    #             )
    #         )
    #
    #         # ---------------------------------------------------------
    #         # CREATE NORMAL + EXCHANGE LINES
    #         # ---------------------------------------------------------
    #
    #         if grouped:
    #             self.env[
    #                 'nhcl.daily.sale.report.line'
    #             ].create(
    #                 list(grouped.values())
    #             )
    #
    #         # ---------------------------------------------------------
    #         # CREATE ROUNDING UP LINE
    #         # ---------------------------------------------------------
    #
    #         if rounding_amount != 0:
    #
    #             if not rounding_product:
    #                 raise ValidationError(
    #                     "Rounding Up product is not available in Products."
    #                 )
    #
    #             last_order = orders[-1] if orders else False
    #
    #             self.env[
    #                 'nhcl.daily.sale.report.line'
    #             ].create({
    #
    #                 'family_name': '',
    #                 'category_name': '',
    #                 'class_name': '',
    #                 'brick_name': 'Rounding Up',
    #
    #                 'bill_qty': 0.0,
    #
    #                 'storable_qty': 0.0,
    #
    #                 'net_amount': rounding_amount,
    #
    #                 'nhcl_company_id':
    #                     store.nhcl_company_id.id,
    #
    #                 'from_date':
    #                     store.from_date,
    #
    #                 'to_date':
    #                     store.to_date,
    #
    #                 'config_id':
    #                     last_order.config_id.id
    #                     if last_order
    #                     else False,
    #
    #                 'nhcl_config_id':
    #                     last_order.config_id.name
    #                     if last_order
    #                     else '',
    #
    #                 'nhcl_daily_sale_report_id':
    #                     self.id,
    #             })
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Daily sale DSD Report',
    #         'res_model': 'nhcl.daily.sale.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [
    #             (
    #                 'nhcl_daily_sale_report_id',
    #                 '=',
    #                 self.id
    #             )
    #         ],
    #     }


    def daily_sale_dsd_report(self):
        self.nhcl_daily_sale_report_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            # ---------------------------------------------------------
            # POS ORDER LINE DOMAIN
            # ---------------------------------------------------------

            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
            ]

            # ---------------------------------------------------------
            # CATEGORY FILTERS
            # ---------------------------------------------------------

            if store.family:
                domain.append(
                    (
                        'product_id.categ_id.parent_id.parent_id.parent_id',
                        '=',
                        store.family.id
                    )
                )

            if store.category:
                domain.append(
                    (
                        'product_id.categ_id.parent_id.parent_id',
                        '=',
                        store.category.id
                    )
                )

            if store.nhcl_class:
                domain.append(
                    (
                        'product_id.categ_id.parent_id',
                        '=',
                        store.nhcl_class.id
                    )
                )

            if store.brick:
                domain.append(
                    (
                        'product_id.categ_id',
                        '=',
                        store.brick.id
                    )
                )

            # ---------------------------------------------------------
            # FETCH POS ORDER LINES
            # ---------------------------------------------------------

            pos_lines = self.env['pos.order.line'].search(domain)

            # ---------------------------------------------------------
            # GET RELATED ORDERS
            # ---------------------------------------------------------

            orders = pos_lines.mapped('order_id')

            # ---------------------------------------------------------
            # TOTAL POS AMOUNT
            # Used only for ROUNDING UP
            # ---------------------------------------------------------

            total_price_subtotal_incl = sum(
                pos_lines.mapped('price_subtotal_incl')
            )

            # ---------------------------------------------------------
            # TOTAL AMOUNT PAID
            # Used only for ROUNDING UP
            # ---------------------------------------------------------

            amount_paid_total = sum(
                orders.mapped('amount_paid')
            )

            # ---------------------------------------------------------
            # ROUNDING DIFFERENCE
            # ---------------------------------------------------------

            rounding_amount = (
                    amount_paid_total - total_price_subtotal_incl
            )

            # ---------------------------------------------------------
            # ROUNDING UP PRODUCT
            # ---------------------------------------------------------

            rounding_product = self.env['product.product'].search([
                ('name', '=', 'Rounding Up')
            ], limit=1)

            # ---------------------------------------------------------
            # CATEGORY CACHE
            # ---------------------------------------------------------

            categ_cache = {}

            def get_categ_names(categ):

                if not categ:
                    return '', '', '', ''

                if categ.id in categ_cache:
                    return categ_cache[categ.id]

                family = (
                    categ.parent_id.parent_id.parent_id.name
                    if categ.parent_id
                       and categ.parent_id.parent_id
                       and categ.parent_id.parent_id.parent_id
                    else ''
                )

                category = (
                    categ.parent_id.parent_id.name
                    if categ.parent_id
                       and categ.parent_id.parent_id
                    else ''
                )

                class_name = (
                    categ.parent_id.name
                    if categ.parent_id
                    else ''
                )

                brick = categ.name or ''

                categ_cache[categ.id] = (
                    family,
                    category,
                    class_name,
                    brick,
                )

                return categ_cache[categ.id]

            # ---------------------------------------------------------
            # GROUP NORMAL POS LINES
            # ---------------------------------------------------------

            grouped = {}

            for line in pos_lines:

                product = line.product_id

                if not product:
                    continue

                categ = product.categ_id

                family, category, class_name, brick = (
                    get_categ_names(categ)
                )

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

                        # ALL PRODUCT TYPES
                        'bill_qty': 0.0,

                        # ONLY STORABLE
                        'storable_qty': 0.0,

                        'net_amount': 0.0,

                        'nhcl_company_id':
                            store.nhcl_company_id.id,

                        'from_date':
                            store.from_date,

                        'to_date':
                            store.to_date,

                        'config_id':
                            line.order_id.config_id.id,

                        'nhcl_config_id':
                            line.order_id.config_id.name,

                        # NEW FIELDS
                        'nhcl_bill_receipt': '',
                        'return_counter': '',

                        'nhcl_daily_sale_report_id':
                            self.id,
                    }

                # -----------------------------------------------------
                # BILL QTY
                # IMPORTANT:
                # ALL TYPES
                # EXCHANGE WILL NEVER MODIFY THIS
                # -----------------------------------------------------

                grouped[key]['bill_qty'] += line.qty

                # -----------------------------------------------------
                # STORABLE QTY
                # ONLY detailed_type == product
                # -----------------------------------------------------

                if product.detailed_type == 'product':
                    grouped[key]['storable_qty'] += line.qty

                # -----------------------------------------------------
                # NET AMOUNT
                # Existing calculation
                # -----------------------------------------------------

                grouped[key]['net_amount'] += (
                    line.price_subtotal_incl
                )

            # ---------------------------------------------------------
            # EXCHANGE MOVES
            # ---------------------------------------------------------

            exchange_domain = [
                ('picking_id.date_done', '>=', from_date),
                ('picking_id.date_done', '<=', to_date),
                ('picking_id.stock_picking_type', '=', 'exchange'),
                ('picking_id.state', '=', 'done'),
                ('nhcl_exchange', '=', True),
                ('company_id', '=', store.nhcl_company_id.id),
            ]

            exchange_moves = self.env['stock.move'].search(
                exchange_domain
            )

            # ---------------------------------------------------------
            # CREATE NORMAL LINES FIRST
            # ---------------------------------------------------------

            if grouped:
                self.env[
                    'nhcl.daily.sale.report.line'
                ].create(
                    list(grouped.values())
                )

            # ---------------------------------------------------------
            # EXCHANGE LINES
            #
            # IMPORTANT:
            # NO GROUPING
            #
            # Every exchange stock.move creates
            # ONE SEPARATE REPORT LINE.
            #
            # Exchange values are NEGATIVE.
            # ---------------------------------------------------------

            exchange_vals_list = []

            for move in exchange_moves:

                product = move.product_id

                if not product:
                    continue

                categ = product.categ_id

                family, category, class_name, brick = (
                    get_categ_names(categ)
                )

                # -----------------------------------------------------
                # BILL RECEIPT
                #
                # stock.picking.nhcl_pos_order
                #     -> pos.order
                #     -> pos_reference
                #
                # If POS order doesn't exist -> empty
                # -----------------------------------------------------

                bill_receipt = ''

                picking = move.picking_id

                if picking.nhcl_pos_order:
                    bill_receipt = (
                            picking.nhcl_pos_order.pos_reference or ''
                    )

                # -----------------------------------------------------
                # RETURN COUNTER
                #
                # stock.picking.return_counter
                # Many2one -> display_name
                # -----------------------------------------------------

                return_counter = ''

                if picking.return_counter:
                    return_counter = (
                        picking.return_counter.display_name
                    )

                # -----------------------------------------------------
                # EXCHANGE VALUES
                # -----------------------------------------------------

                exchange_qty = (
                    -(move.quantity or 0.0)
                )

                exchange_amount = (
                    -(move.nhcl_price_total or 0.0)
                )

                # -----------------------------------------------------
                # SEPARATE EXCHANGE LINE
                # -----------------------------------------------------

                exchange_vals_list.append({

                    'family_name': family,

                    'category_name': category,

                    'class_name': class_name,

                    'brick_name': brick,

                    # Exchange should NOT affect bill_qty
                    'bill_qty': 0.0,

                    # Exchange quantity NEGATIVE
                    'storable_qty': exchange_qty,

                    # Exchange amount NEGATIVE
                    'net_amount': exchange_amount,

                    'nhcl_company_id':
                        store.nhcl_company_id.id,

                    'from_date':
                        store.from_date,

                    'to_date':
                        store.to_date,

                    # Exchange does not have POS config
                    'config_id': False,

                    'nhcl_config_id': '',

                    # POS Reference
                    'nhcl_bill_receipt': bill_receipt,

                    # Return Counter
                    'return_counter': return_counter,

                    'nhcl_daily_sale_report_id':
                        self.id,
                })

            # ---------------------------------------------------------
            # CREATE EXCHANGE LINES
            # ---------------------------------------------------------

            if exchange_vals_list:
                self.env[
                    'nhcl.daily.sale.report.line'
                ].create(exchange_vals_list)

            # ---------------------------------------------------------
            # DEBUG
            # ---------------------------------------------------------

            normal_bill_qty = sum(
                line.qty for line in pos_lines
            )

            normal_storable_qty = sum(
                line.qty
                for line in pos_lines
                if line.product_id
                and line.product_id.detailed_type == 'product'
            )

            normal_amount = sum(
                line.price_subtotal_incl
                for line in pos_lines
            )

            exchange_qty_total = sum(
                move.quantity or 0.0
                for move in exchange_moves
            )

            exchange_amount_total = sum(
                move.nhcl_price_total or 0.0
                for move in exchange_moves
            )

            final_storable_qty = (
                    normal_storable_qty
                    - exchange_qty_total
            )

            final_amount = (
                    normal_amount
                    - exchange_amount_total
            )



            # ---------------------------------------------------------
            # CREATE ROUNDING UP LINE
            # ---------------------------------------------------------

            if rounding_amount != 0:

                if not rounding_product:
                    raise ValidationError(
                        "Rounding Up product is not available in Products."
                    )

                last_order = orders[-1] if orders else False

                self.env[
                    'nhcl.daily.sale.report.line'
                ].create({

                    'family_name': '',
                    'category_name': '',
                    'class_name': '',
                    'brick_name': 'Rounding Up',

                    'bill_qty': 0.0,

                    'storable_qty': 0.0,

                    'net_amount': rounding_amount,

                    'nhcl_company_id':
                        store.nhcl_company_id.id,

                    'from_date':
                        store.from_date,

                    'to_date':
                        store.to_date,

                    'config_id':
                        last_order.config_id.id
                        if last_order
                        else False,

                    'nhcl_config_id':
                        last_order.config_id.name
                        if last_order
                        else '',

                    # NEW FIELDS
                    'nhcl_bill_receipt': '',
                    'return_counter': '',

                    'nhcl_daily_sale_report_id':
                        self.id,
                })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily sale DSD Report',
            'res_model': 'nhcl.daily.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                (
                    'nhcl_daily_sale_report_id',
                    '=',
                    self.id
                )
            ],
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

    from_date = fields.Datetime(string="From Date")
    to_date = fields.Datetime(string="To Date")
    nhcl_daily_sale_report_id = fields.Many2one('nhcl.daily.sale.report', string="Daily Sale Report")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    bill_qty = fields.Float(string="BillQty(service prdct)", digits="Product Unit of Measure")
    net_amount = fields.Float(string="Total Amount")
    config_id = fields.Many2one('pos.config', string='Terminal')
    nhcl_config_id = fields.Char(string="Terminal")
    storable_qty = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure"
    )
    nhcl_bill_receipt = fields.Char(
        string='Bill Receipt'
    )

    return_counter = fields.Char(
        string='Return Counter'
    )
