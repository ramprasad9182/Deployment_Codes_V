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


class NhclDailySaleDetailedReport(models.Model):
    _name = 'nhcl.daily.sale.detailed.report'
    _description = "Daily Sale Detailed Report"
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
    nhcl_daily_sale_detailed_report_ids = fields.One2many('nhcl.daily.sale.detailed.report.line', 'nhcl_daily_sale_detailed_report_id')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name', default=lambda self: self.env.company)
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




    # def daily_sale_detailed_report(self):
    #     self.nhcl_daily_sale_detailed_report_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #         domain = [
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #             ('order_id.company_id', '=', store.nhcl_company_id.id),
    #             ('order_id.state', '=', 'invoiced'),
    #             ('product_id.detailed_type', '=', 'product'),
    #             ('order_id.refunded_orders_count', '=', 0)
    #         ]
    #
    #         # Terminal filter
    #         if store.config_id:
    #             domain.append(
    #                 ('order_id.config_id', '=', store.config_id.id)
    #             )
    #
    #         # Cashier filter
    #         if store.cashier_id:
    #             domain.append(
    #                 ('order_id.employee_id', '=', store.cashier_id.id)
    #             )
    #
    #         # Brick filter
    #         if store.brick:
    #             domain.append(
    #                 ('product_id.categ_id', '=', store.brick.id)
    #             )
    #
    #         # Product filter
    #         if store.product_id:
    #             domain.append(
    #                 ('product_id', '=', store.product_id.id)
    #             )
    #
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         report_vals = []
    #
    #         # ---------------------------------------------------------
    #         # ROUNDING PRODUCT
    #         # ---------------------------------------------------------
    #         rounding_up_product = self.env['product.product'].search([
    #             ('name', '=', 'Rounding Up')
    #         ], limit=1)
    #
    #         if not rounding_up_product:
    #             raise ValidationError(
    #                 _("Product 'Rounding Up' not found. Please create the product.")
    #             )
    #
    #         lot_cache = {}
    #
    #         # =========================================================
    #         # NORMAL POS SALE LINES
    #         # =========================================================
    #
    #         for line in pos_lines:
    #             product = line.product_id
    #             categ = product.categ_id
    #
    #             # -----------------------------------------------------
    #             # PRICE POINT FILTER
    #             # -----------------------------------------------------
    #             if store.price_point and line.price_unit != store.price_point:
    #                 continue
    #
    #             # -----------------------------------------------------
    #             # SERIAL / LOT
    #             # -----------------------------------------------------
    #             serial_id = False
    #
    #             if line.pack_lot_ids:
    #                 lot_name = line.pack_lot_ids[0].display_name
    #
    #                 if lot_name:
    #                     if lot_name not in lot_cache:
    #                         lot_cache[lot_name] = self.env['stock.lot'].search(
    #                             [('name', '=', lot_name)],
    #                             limit=1
    #                         )
    #
    #                     serial_id = lot_cache[lot_name]
    #
    #             # -----------------------------------------------------
    #             # FAMILY / CATEGORY / CLASS / BRICK
    #             # -----------------------------------------------------
    #             family = ''
    #             category_name = ''
    #             class_name = ''
    #             brick_name = ''
    #
    #             family_rec = False
    #             category_rec = False
    #             class_rec = False
    #             brick_rec = False
    #
    #             if categ:
    #                 parent_ids = [
    #                     int(x)
    #                     for x in (categ.parent_path or '').rstrip('/').split('/')
    #                     if x
    #                 ]
    #
    #                 # 1st level -> Family
    #                 if len(parent_ids) >= 1:
    #                     family_rec = self.env['product.category'].browse(
    #                         parent_ids[0]
    #                     )
    #                     family = family_rec.name or ''
    #
    #                 # 2nd level -> Category
    #                 if len(parent_ids) >= 2:
    #                     category_rec = self.env['product.category'].browse(
    #                         parent_ids[1]
    #                     )
    #                     category_name = category_rec.name or ''
    #
    #                 # 3rd level -> Class
    #                 if len(parent_ids) >= 3:
    #                     class_rec = self.env['product.category'].browse(
    #                         parent_ids[2]
    #                     )
    #                     class_name = class_rec.name or ''
    #
    #                 # 4th level -> Brick
    #                 if len(parent_ids) >= 4:
    #                     brick_rec = self.env['product.category'].browse(
    #                         parent_ids[3]
    #                     )
    #                     brick_name = brick_rec.name or ''
    #
    #             # -----------------------------------------------------
    #             # FAMILY FILTER
    #             # -----------------------------------------------------
    #             if store.family and family_rec != store.family:
    #                 continue
    #
    #             # -----------------------------------------------------
    #             # CATEGORY FILTER
    #             # -----------------------------------------------------
    #             if store.category and category_rec != store.category:
    #                 continue
    #
    #             # -----------------------------------------------------
    #             # CLASS FILTER
    #             # -----------------------------------------------------
    #             if store.nhcl_class and class_rec != store.nhcl_class:
    #                 continue
    #
    #             # -----------------------------------------------------
    #             # AGING FILTER
    #             # -----------------------------------------------------
    #             if store.aging:
    #                 if not serial_id or serial_id.description_1 != store.aging:
    #                     continue
    #
    #             # -----------------------------------------------------
    #             # UNBRAND SERIAL FILTER
    #             # -----------------------------------------------------
    #             if store.unbrand_serial:
    #                 if not serial_id or serial_id != store.unbrand_serial:
    #                     continue
    #
    #             # -----------------------------------------------------
    #             # BRANDED BARCODE FILTER
    #             # -----------------------------------------------------
    #             if store.branded_barcode:
    #                 if not serial_id or serial_id.ref != store.branded_barcode:
    #                     continue
    #
    #             # -----------------------------------------------------
    #             # BRAND FILTER
    #             # -----------------------------------------------------
    #             if store.brand:
    #                 if not serial_id or serial_id.category_3 != store.brand:
    #                     continue
    #
    #             # =====================================================
    #             # CALCULATED TAX
    #             # =====================================================
    #
    #             subtotal = line.price_subtotal or 0.0
    #             tax_inc_total = line.price_subtotal_incl or 0.0
    #
    #             calculated_tax_amount = (
    #                     tax_inc_total - subtotal
    #             )
    #
    #             # -----------------------------------------------------
    #             # LINE LEVEL DISCOUNT
    #             # -----------------------------------------------------
    #             line_discount = 0.0
    #
    #             if hasattr(line, 'discount') and line.discount:
    #                 line_discount = (
    #                                         line.price_unit * line.qty
    #                                 ) * (line.discount / 100.0)
    #
    #             elif hasattr(line, 'price_ih_discount'):
    #                 line_discount = line.price_ih_discount
    #
    #             # =====================================================
    #             # REPORT LINE
    #             # =====================================================
    #
    #             report_vals.append({
    #
    #                 # -------------------------------------------------
    #                 # CATEGORY DETAILS
    #                 # -------------------------------------------------
    #                 'family_name': family,
    #                 'category_name': category_name,
    #                 'class_name': class_name,
    #                 'brick_name': brick_name,
    #
    #                 # -------------------------------------------------
    #                 # PRODUCT
    #                 # -------------------------------------------------
    #                 'product_name': product.name,
    #                 'hsn': product.l10n_in_hsn_code or '',
    #                 'uom': product.uom_id.name or '',
    #
    #                 # -------------------------------------------------
    #                 # PROMO / NOTE
    #                 # -------------------------------------------------
    #                 'promo': (
    #                     line.nhcl_reward_id.display_name
    #                     if line.nhcl_reward_id
    #                     else ''
    #                 ),
    #
    #                 'customer_note': line.order_id.note,
    #
    #                 # -------------------------------------------------
    #                 # SERIAL DETAILS
    #                 # -------------------------------------------------
    #                 'colour': (
    #                     serial_id.category_1.name
    #                     if serial_id and serial_id.category_1
    #                     else ''
    #                 ),
    #
    #                 'aging': (
    #                     serial_id.description_1.name
    #                     if serial_id and serial_id.description_1
    #                     else ''
    #                 ),
    #
    #                 'fit': (
    #                     serial_id.category_2.name
    #                     if serial_id and serial_id.category_2
    #                     else ''
    #                 ),
    #
    #                 'design': (
    #                     serial_id.category_8.name
    #                     if serial_id and serial_id.category_8
    #                     else ''
    #                 ),
    #
    #                 'brand': (
    #                     serial_id.category_3.name
    #                     if serial_id and serial_id.category_3
    #                     else ''
    #                 ),
    #
    #                 'size': (
    #                     serial_id.category_7.name
    #                     if serial_id and serial_id.category_7
    #                     else ''
    #                 ),
    #
    #                 'barcode': (
    #                     serial_id.ref
    #                     if serial_id
    #                     else ''
    #                 ),
    #
    #                 'serial': (
    #                     serial_id.name
    #                     if serial_id
    #                     else ''
    #                 ),
    #
    #                 # -------------------------------------------------
    #                 # QUANTITY / PRICE
    #                 # -------------------------------------------------
    #                 'bill_qty': line.qty,
    #                 'mrp': line.nhcl_mr_price,
    #                 'rsp_amount': line.price_unit,
    #
    #                 # -------------------------------------------------
    #                 # TAX PERCENT
    #                 # -------------------------------------------------
    #                 'tax_persent': ', '.join(
    #                     line.tax_ids_after_fiscal_position.mapped('name')
    #                 ) if line.tax_ids_after_fiscal_position else '',
    #
    #                 # -------------------------------------------------
    #                 # TAX AMOUNT
    #                 # -------------------------------------------------
    #                 'tax_amount': calculated_tax_amount,
    #
    #                 # -------------------------------------------------
    #                 # SALE / NET
    #                 # -------------------------------------------------
    #                 'sale_amount': line.price_subtotal_incl,
    #                 'net_amount': line.price_subtotal_incl,
    #
    #                 # -------------------------------------------------
    #                 # DISCOUNT
    #                 # -------------------------------------------------
    #                 'discount': line_discount,
    #
    #                 # -------------------------------------------------
    #                 # SUBTOTAL
    #                 # -------------------------------------------------
    #                 'price_subtotal': line.price_subtotal,
    #
    #                 # -------------------------------------------------
    #                 # POS DETAILS
    #                 # -------------------------------------------------
    #                 'config_id': line.order_id.config_id.id,
    #                 'employee_id': line.employ_id.id if line.employ_id else False,
    #                 'badge_id': line.badge_id or '',
    #                 'cashier_id': line.order_id.employee_id.id,
    #                 'nhcl_bill_receipt': line.order_id.pos_reference,
    #                 'nhcl_date_order': line.order_id.date_order,
    #
    #                 # -------------------------------------------------
    #                 # COMPANY / REPORT
    #                 # -------------------------------------------------
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'nhcl_daily_sale_detailed_report_id': self.id,
    #             })
    #
    #         # =========================================================
    #         # ROUNDING
    #         # =========================================================
    #
    #         line_total = sum(
    #             pos_lines.mapped('price_subtotal_incl')
    #         )
    #
    #         orders = pos_lines.mapped('order_id')
    #
    #         amount_paid_total = sum(
    #             orders.mapped('amount_paid')
    #         )
    #
    #         rounding_difference = (
    #                 amount_paid_total - line_total
    #         )
    #
    #         if rounding_difference:
    #             report_vals.append({
    #
    #                 'product_name': rounding_up_product.name or 'Rounding Up',
    #
    #                 'hsn': rounding_up_product.l10n_in_hsn_code or '',
    #
    #                 'uom': rounding_up_product.uom_id.name or '',
    #
    #                 'bill_qty': 0.0,
    #
    #                 'mrp': 0.0,
    #
    #                 'rsp_amount': rounding_difference,
    #
    #                 'price_subtotal': rounding_difference,
    #
    #                 'net_amount': rounding_difference,
    #
    #                 'sale_amount': rounding_difference,
    #
    #                 'tax_amount': 0.0,
    #
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #
    #                 'nhcl_daily_sale_detailed_report_id': self.id,
    #             })
    #
    #         # =========================================================
    #         # POS EXCHANGE
    #         # =========================================================
    #
    #         exchange_pickings = self.env['stock.picking'].search([
    #             ('date_done', '>=', from_date),
    #             ('date_done', '<=', to_date),
    #             ('stock_picking_type', '=', 'exchange'),
    #             ('state', '=', 'done'),
    #             ('company_id', '=', store.nhcl_company_id.id),
    #         ])
    #
    #         for picking in exchange_pickings:
    #
    #             # -------------------------------------------------
    #             # CONFIG_ID FROM STOCK.PICKING VIA RETURN_COUNTER
    #             # -------------------------------------------------
    #             picking_config_id = False
    #             if hasattr(picking, 'return_counter') and picking.return_counter:
    #                 picking_config_id = picking.return_counter.id
    #
    #             exchange_moves = picking.move_ids.filtered(
    #                 lambda move: move.nhcl_exchange is True
    #             )
    #
    #             for move in exchange_moves:
    #
    #                 product = move.product_id
    #
    #                 if not product:
    #                     continue
    #
    #                 pos_order_line = self.env['pos.order.line'].search([
    #                     ('order_id', '=', picking.nhcl_pos_order.id),
    #                     ('product_id', '=', product.id),
    #                 ], limit=1)
    #
    #                 employee_id = (
    #                     pos_order_line.employ_id.id
    #                     if pos_order_line and pos_order_line.employ_id
    #                     else False
    #                 )
    #
    #                 badge_id = (
    #                     pos_order_line.badge_id
    #                     if pos_order_line
    #                     else ''
    #                 )
    #
    #                 categ = product.categ_id
    #
    #                 # -------------------------------------------------
    #                 # FAMILY / CATEGORY / CLASS / BRICK
    #                 # -------------------------------------------------
    #
    #                 family = ''
    #                 category_name = ''
    #                 class_name = ''
    #                 brick_name = ''
    #
    #                 family_rec = False
    #                 category_rec = False
    #                 class_rec = False
    #                 brick_rec = False
    #
    #                 if categ:
    #                     parent_ids = [
    #                         int(x)
    #                         for x in (categ.parent_path or '').rstrip('/').split('/')
    #                         if x
    #                     ]
    #
    #                     # Family
    #                     if len(parent_ids) >= 1:
    #                         family_rec = self.env[
    #                             'product.category'
    #                         ].browse(parent_ids[0])
    #
    #                         family = family_rec.name or ''
    #
    #                     # Category
    #                     if len(parent_ids) >= 2:
    #                         category_rec = self.env[
    #                             'product.category'
    #                         ].browse(parent_ids[1])
    #
    #                         category_name = category_rec.name or ''
    #
    #                     # Class
    #                     if len(parent_ids) >= 3:
    #                         class_rec = self.env[
    #                             'product.category'
    #                         ].browse(parent_ids[2])
    #
    #                         class_name = class_rec.name or ''
    #
    #                     # Brick
    #                     if len(parent_ids) >= 4:
    #                         brick_rec = self.env[
    #                             'product.category'
    #                         ].browse(parent_ids[3])
    #
    #                         brick_name = brick_rec.name or ''
    #
    #                 # -------------------------------------------------
    #                 # LOT / SERIAL ATTRIBUTES (Exchange)
    #                 # -------------------------------------------------
    #
    #                 serial_id = move.lot_ids[:1]
    #
    #                 hsn = (
    #                     serial_id.nhcl_lot_hsn_code or ''
    #                     if serial_id
    #                     else ''
    #                 )
    #
    #                 serial = (
    #                     serial_id.name or ''
    #                     if serial_id
    #                     else ''
    #                 )
    #
    #                 barcode = (
    #                     serial_id.ref or ''
    #                     if serial_id
    #                     else ''
    #                 )
    #
    #                 colour = (
    #                     serial_id.category_1.name
    #                     if serial_id and serial_id.category_1
    #                     else ''
    #                 )
    #
    #                 aging = (
    #                     serial_id.description_1.name
    #                     if serial_id and serial_id.description_1
    #                     else ''
    #                 )
    #
    #                 fit = (
    #                     serial_id.category_2.name
    #                     if serial_id and serial_id.category_2
    #                     else ''
    #                 )
    #
    #                 design = (
    #                     serial_id.category_8.name
    #                     if serial_id and serial_id.category_8
    #                     else ''
    #                 )
    #
    #                 brand = (
    #                     serial_id.category_3.name
    #                     if serial_id and serial_id.category_3
    #                     else ''
    #                 )
    #
    #                 size = (
    #                     serial_id.category_7.name
    #                     if serial_id and serial_id.category_7
    #                     else ''
    #                 )
    #
    #                 # -------------------------------------------------
    #                 # TAX
    #                 # -------------------------------------------------
    #
    #                 tax_persent = ', '.join(
    #                     move.nhcl_tax_ids.mapped('name')
    #                 ) if move.nhcl_tax_ids else ''
    #
    #                 # -------------------------------------------------
    #                 # EXCHANGE VALUES
    #                 # -------------------------------------------------
    #
    #                 exchange_qty = -(
    #                         move.quantity or 0.0
    #                 )
    #
    #                 exchange_rsp = -(
    #                         move.nhcl_rsp or 0.0
    #                 )
    #
    #                 exchange_subtotal = -(
    #                         move.nhcl_price_subtotal or 0.0
    #                 )
    #
    #                 exchange_net_amount = -(
    #                         move.nhcl_price_total or 0.0
    #                 )
    #
    #                 exchange_tax_amount = -(
    #                         (move.nhcl_price_total or 0.0) - (move.nhcl_price_subtotal or 0.0)
    #                 )
    #
    #                 exchange_discount = -(
    #                         move.nhcl_discount or 0.0
    #                 )
    #
    #                 # -------------------------------------------------
    #                 # EXCHANGE REPORT LINE
    #                 # -------------------------------------------------
    #
    #                 report_vals.append({
    #
    #                     'family_name': family,
    #                     'category_name': category_name,
    #                     'class_name': class_name,
    #                     'brick_name': brick_name,
    #
    #                     'product_name': product.name,
    #
    #                     'hsn': hsn,
    #
    #                     'uom': product.uom_id.name or '',
    #
    #                     'promo': '',
    #                     'customer_note': '',
    #
    #                     'colour': colour,
    #                     'aging': aging,
    #                     'fit': fit,
    #                     'design': design,
    #                     'brand': brand,
    #                     'size': size,
    #
    #                     'barcode': barcode,
    #                     'serial': serial,
    #
    #                     # Exchange Qty
    #                     'bill_qty': exchange_qty,
    #
    #                     'mrp': 0.0,
    #
    #                     # Exchange RSP
    #                     'rsp_amount': exchange_rsp,
    #
    #                     # Tax %
    #                     'tax_persent': tax_persent,
    #
    #                     # Exchange Tax
    #                     'tax_amount': exchange_tax_amount,
    #
    #                     # Sale Amount
    #                     'sale_amount': 0.0,
    #
    #                     # Exchange Net
    #                     'net_amount': exchange_net_amount,
    #
    #                     # Exchange Discount
    #                     'discount': exchange_discount,
    #
    #                     # Exchange Subtotal
    #                     'price_subtotal': exchange_subtotal,
    #
    #                     'config_id': picking_config_id,
    #                     'cashier_id': False,
    #
    #                     # Picking reference
    #                     'nhcl_bill_receipt': (
    #                         picking.nhcl_pos_order.pos_reference
    #                         if picking.nhcl_pos_order
    #                         else ''
    #                     ),
    #
    #                     'nhcl_date_order': picking.date_done,
    #
    #                     'nhcl_company_id': store.nhcl_company_id.id,
    #
    #                     'nhcl_daily_sale_detailed_report_id': self.id,
    #                     'employee_id': employee_id,
    #                     'badge_id': badge_id,
    #                 })
    #
    #         # =========================================================
    #         # CREATE ALL REPORT LINES
    #         # =========================================================
    #
    #         if report_vals:
    #             self.env[
    #                 'nhcl.daily.sale.detailed.report.line'
    #             ].create(report_vals)
    #
    #     # =============================================================
    #     # OPEN REPORT
    #     # =============================================================
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Daily Sale Detailed Report',
    #         'res_model': 'nhcl.daily.sale.detailed.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [
    #             (
    #                 'nhcl_daily_sale_detailed_report_id',
    #                 '=',
    #                 self.id
    #             )
    #         ],
    #         'context': {
    #             'default_nhcl_daily_sale_detailed_report_id': self.id
    #         }
    #     }

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

            # Terminal filter
            if store.config_id:
                domain.append(
                    ('order_id.config_id', '=', store.config_id.id)
                )

            # Cashier filter
            if store.cashier_id:
                domain.append(
                    ('order_id.employee_id', '=', store.cashier_id.id)
                )

            # Brick filter
            if store.brick:
                domain.append(
                    ('product_id.categ_id', '=', store.brick.id)
                )

            # Product filter
            if store.product_id:
                domain.append(
                    ('product_id', '=', store.product_id.id)
                )

            pos_lines = self.env['pos.order.line'].search(domain)

            report_vals = []

            # ---------------------------------------------------------
            # ROUNDING PRODUCT
            # ---------------------------------------------------------
            rounding_up_product = self.env['product.product'].search([
                ('name', '=', 'Rounding Up')
            ], limit=1)

            if not rounding_up_product:
                raise ValidationError(
                    _("Product 'Rounding Up' not found. Please create the product.")
                )

            lot_cache = {}

            # =========================================================
            # NORMAL POS SALE LINES
            # =========================================================

            for line in pos_lines:
                product = line.product_id
                categ = product.categ_id

                # -----------------------------------------------------
                # PRICE POINT FILTER
                # -----------------------------------------------------
                if store.price_point and line.price_unit != store.price_point:
                    continue

                # -----------------------------------------------------
                # SERIAL / LOT
                # -----------------------------------------------------
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

                # -----------------------------------------------------
                # FAMILY / CATEGORY / CLASS / BRICK
                # -----------------------------------------------------
                family = ''
                category_name = ''
                class_name = ''
                brick_name = ''

                family_rec = False
                category_rec = False
                class_rec = False
                brick_rec = False

                if categ:
                    parent_ids = [
                        int(x)
                        for x in (categ.parent_path or '').rstrip('/').split('/')
                        if x
                    ]

                    # 1st level -> Family
                    if len(parent_ids) >= 1:
                        family_rec = self.env['product.category'].browse(
                            parent_ids[0]
                        )
                        family = family_rec.name or ''

                    # 2nd level -> Category
                    if len(parent_ids) >= 2:
                        category_rec = self.env['product.category'].browse(
                            parent_ids[1]
                        )
                        category_name = category_rec.name or ''

                    # 3rd level -> Class
                    if len(parent_ids) >= 3:
                        class_rec = self.env['product.category'].browse(
                            parent_ids[2]
                        )
                        class_name = class_rec.name or ''

                    # 4th level -> Brick
                    if len(parent_ids) >= 4:
                        brick_rec = self.env['product.category'].browse(
                            parent_ids[3]
                        )
                        brick_name = brick_rec.name or ''

                # -----------------------------------------------------
                # FAMILY FILTER
                # -----------------------------------------------------
                if store.family and family_rec != store.family:
                    continue

                # -----------------------------------------------------
                # CATEGORY FILTER
                # -----------------------------------------------------
                if store.category and category_rec != store.category:
                    continue

                # -----------------------------------------------------
                # CLASS FILTER
                # -----------------------------------------------------
                if store.nhcl_class and class_rec != store.nhcl_class:
                    continue

                # -----------------------------------------------------
                # AGING FILTER
                # -----------------------------------------------------
                if store.aging:
                    if not serial_id or serial_id.description_1 != store.aging:
                        continue

                # -----------------------------------------------------
                # UNBRAND SERIAL FILTER
                # -----------------------------------------------------
                if store.unbrand_serial:
                    if not serial_id or serial_id != store.unbrand_serial:
                        continue

                # -----------------------------------------------------
                # BRANDED BARCODE FILTER
                # -----------------------------------------------------
                if store.branded_barcode:
                    if not serial_id or serial_id.ref != store.branded_barcode:
                        continue

                # -----------------------------------------------------
                # BRAND FILTER
                # -----------------------------------------------------
                if store.brand:
                    if not serial_id or serial_id.category_3 != store.brand:
                        continue

                # =====================================================
                # CALCULATED TAX
                # =====================================================

                subtotal = line.price_subtotal or 0.0
                tax_inc_total = line.price_subtotal_incl or 0.0

                calculated_tax_amount = (
                        tax_inc_total - subtotal
                )

                # -----------------------------------------------------
                # LINE LEVEL DISCOUNT
                # -----------------------------------------------------
                line_discount = 0.0

                if hasattr(line, 'discount') and line.discount:
                    line_discount = (
                                            line.price_unit * line.qty
                                    ) * (line.discount / 100.0)

                elif hasattr(line, 'price_ih_discount'):
                    line_discount = line.price_ih_discount

                # =====================================================
                # REPORT LINE
                # =====================================================

                report_vals.append({

                    # -------------------------------------------------
                    # CATEGORY DETAILS
                    # -------------------------------------------------
                    'family_name': family,
                    'category_name': category_name,
                    'class_name': class_name,
                    'brick_name': brick_name,

                    # -------------------------------------------------
                    # PRODUCT
                    # -------------------------------------------------
                    'product_name': product.name,
                    'hsn': product.l10n_in_hsn_code or '',
                    'uom': product.uom_id.name or '',

                    # -------------------------------------------------
                    # PROMO / NOTE
                    # -------------------------------------------------
                    'promo': (
                        line.nhcl_reward_id.display_name
                        if line.nhcl_reward_id
                        else ''
                    ),

                    'customer_note': line.order_id.note,

                    # -------------------------------------------------
                    # SERIAL DETAILS
                    # -------------------------------------------------
                    'colour': (
                        serial_id.category_1.name
                        if serial_id and serial_id.category_1
                        else ''
                    ),

                    'aging': (
                        serial_id.description_1.name
                        if serial_id and serial_id.description_1
                        else ''
                    ),

                    'fit': (
                        serial_id.category_2.name
                        if serial_id and serial_id.category_2
                        else ''
                    ),

                    'design': (
                        serial_id.category_8.name
                        if serial_id and serial_id.category_8
                        else ''
                    ),

                    'brand': (
                        serial_id.category_3.name
                        if serial_id and serial_id.category_3
                        else ''
                    ),

                    'size': (
                        serial_id.category_7.name
                        if serial_id and serial_id.category_7
                        else ''
                    ),

                    'barcode': (
                        serial_id.ref
                        if serial_id
                        else ''
                    ),

                    'serial': (
                        serial_id.name
                        if serial_id
                        else ''
                    ),

                    # -------------------------------------------------
                    # QUANTITY / PRICE
                    # -------------------------------------------------
                    'bill_qty': line.qty,
                    'mrp': line.nhcl_mr_price,
                    'rsp_amount': line.price_unit,

                    # -------------------------------------------------
                    # TAX PERCENT
                    # -------------------------------------------------
                    'tax_persent': ', '.join(
                        line.tax_ids_after_fiscal_position.mapped('name')
                    ) if line.tax_ids_after_fiscal_position else '',

                    # -------------------------------------------------
                    # TAX AMOUNT
                    # -------------------------------------------------
                    'tax_amount': calculated_tax_amount,

                    # -------------------------------------------------
                    # SALE / NET
                    # -------------------------------------------------
                    'sale_amount': line.price_subtotal_incl,
                    'net_amount': line.price_subtotal_incl,

                    # -------------------------------------------------
                    # DISCOUNT
                    # -------------------------------------------------
                    'discount': line.total_discount or 0.0,

                    # -------------------------------------------------
                    # TOTAL REWARD DISCOUNT
                    # -------------------------------------------------
                    'total_reward_discount': (
                            line.total_reward_discount or 0.0
                    ),

                    # -------------------------------------------------
                    # SUBTOTAL
                    # -------------------------------------------------
                    'price_subtotal': line.price_subtotal,

                    # -------------------------------------------------
                    # POS DETAILS
                    # -------------------------------------------------
                    'config_id': line.order_id.config_id.id,
                    'employee_id': line.employ_id.id if line.employ_id else False,
                    'badge_id': line.badge_id or '',
                    'cashier_id': line.order_id.employee_id.id,
                    'nhcl_bill_receipt': line.order_id.pos_reference,
                    'nhcl_date_order': line.order_id.date_order,

                    # -------------------------------------------------
                    # COMPANY / REPORT
                    # -------------------------------------------------
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'nhcl_daily_sale_detailed_report_id': self.id,
                    'from_date': store.from_date,
                    'to_date': store.to_date,

                })

            # =========================================================
            # ROUNDING
            # =========================================================

            line_total = sum(
                pos_lines.mapped('price_subtotal_incl')
            )

            orders = pos_lines.mapped('order_id')

            amount_paid_total = sum(
                orders.mapped('amount_paid')
            )

            rounding_difference = (
                    amount_paid_total - line_total
            )

            if rounding_difference:
                report_vals.append({

                    'product_name': rounding_up_product.name or 'Rounding Up',

                    'hsn': rounding_up_product.l10n_in_hsn_code or '',

                    'uom': rounding_up_product.uom_id.name or '',

                    'bill_qty': 0.0,

                    'mrp': 0.0,

                    'rsp_amount': rounding_difference,

                    'price_subtotal': rounding_difference,

                    'net_amount': rounding_difference,

                    'sale_amount': rounding_difference,

                    'tax_amount': 0.0,

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'nhcl_daily_sale_detailed_report_id': self.id,
                })

            # =========================================================
            # POS EXCHANGE
            # =========================================================

            exchange_pickings = self.env['stock.picking'].search([
                ('date_done', '>=', from_date),
                ('date_done', '<=', to_date),
                ('stock_picking_type', '=', 'exchange'),
                ('state', '=', 'done'),
                ('company_id', '=', store.nhcl_company_id.id),
            ])

            for picking in exchange_pickings:

                # -------------------------------------------------
                # CONFIG_ID FROM STOCK.PICKING VIA RETURN_COUNTER
                # -------------------------------------------------
                picking_config_id = False

                if hasattr(picking, 'return_counter') and picking.return_counter:
                    picking_config_id = picking.return_counter.id

                exchange_moves = picking.move_ids.filtered(
                    lambda move: move.nhcl_exchange is True
                )

                for move in exchange_moves:

                    product = move.product_id

                    if not product:
                        continue

                    # -------------------------------------------------
                    # POS ORDER LINE
                    # -------------------------------------------------
                    pos_order_line = self.env['pos.order.line'].search([
                        ('order_id', '=', picking.nhcl_pos_order.id),
                        ('product_id', '=', product.id),
                    ], limit=1)

                    employee_id = (
                        pos_order_line.employ_id.id
                        if pos_order_line and pos_order_line.employ_id
                        else False
                    )

                    badge_id = (
                        pos_order_line.badge_id
                        if pos_order_line
                        else ''
                    )

                    categ = product.categ_id

                    # -------------------------------------------------
                    # FAMILY / CATEGORY / CLASS / BRICK
                    # -------------------------------------------------
                    family = ''
                    category_name = ''
                    class_name = ''
                    brick_name = ''

                    family_rec = False
                    category_rec = False
                    class_rec = False
                    brick_rec = False

                    if categ:
                        parent_ids = [
                            int(x)
                            for x in (categ.parent_path or '').rstrip('/').split('/')
                            if x
                        ]

                        # Family
                        if len(parent_ids) >= 1:
                            family_rec = self.env[
                                'product.category'
                            ].browse(parent_ids[0])

                            family = family_rec.name or ''

                        # Category
                        if len(parent_ids) >= 2:
                            category_rec = self.env[
                                'product.category'
                            ].browse(parent_ids[1])

                            category_name = category_rec.name or ''

                        # Class
                        if len(parent_ids) >= 3:
                            class_rec = self.env[
                                'product.category'
                            ].browse(parent_ids[2])

                            class_name = class_rec.name or ''

                        # Brick
                        if len(parent_ids) >= 4:
                            brick_rec = self.env[
                                'product.category'
                            ].browse(parent_ids[3])

                            brick_name = brick_rec.name or ''

                    # -------------------------------------------------
                    # LOT / SERIAL ATTRIBUTES (Exchange)
                    # -------------------------------------------------

                    serial_id = move.lot_ids[:1]

                    hsn = (
                        serial_id.nhcl_lot_hsn_code or ''
                        if serial_id
                        else ''
                    )

                    serial = (
                        serial_id.name or ''
                        if serial_id
                        else ''
                    )

                    barcode = (
                        serial_id.ref or ''
                        if serial_id
                        else ''
                    )

                    colour = (
                        serial_id.category_1.name
                        if serial_id and serial_id.category_1
                        else ''
                    )

                    aging = (
                        serial_id.description_1.name
                        if serial_id and serial_id.description_1
                        else ''
                    )

                    fit = (
                        serial_id.category_2.name
                        if serial_id and serial_id.category_2
                        else ''
                    )

                    design = (
                        serial_id.category_8.name
                        if serial_id and serial_id.category_8
                        else ''
                    )

                    brand = (
                        serial_id.category_3.name
                        if serial_id and serial_id.category_3
                        else ''
                    )

                    size = (
                        serial_id.category_7.name
                        if serial_id and serial_id.category_7
                        else ''
                    )

                    # -------------------------------------------------
                    # TAX
                    # -------------------------------------------------

                    tax_persent = ', '.join(
                        move.nhcl_tax_ids.mapped('name')
                    ) if move.nhcl_tax_ids else ''

                    # -------------------------------------------------
                    # EXCHANGE VALUES
                    # -------------------------------------------------

                    exchange_qty = -(
                            move.quantity or 0.0
                    )

                    exchange_rsp = -(
                            move.nhcl_rsp or 0.0
                    )

                    exchange_subtotal = -(
                            move.nhcl_price_subtotal or 0.0
                    )

                    exchange_net_amount = -(
                            move.nhcl_price_total or 0.0
                    )

                    exchange_tax_amount = -(
                            (move.nhcl_price_total or 0.0)
                            - (move.nhcl_price_subtotal or 0.0)
                    )

                    exchange_discount = -(
                            move.total_discount or 0.0
                    )

                    exchange_reward_discount = -(
                            move.total_reward_discount or 0.0
                    )

                    # =================================================
                    # EXCHANGE REPORT LINE
                    # =================================================

                    report_vals.append({

                        'family_name': family,
                        'category_name': category_name,
                        'class_name': class_name,
                        'brick_name': brick_name,

                        'product_name': product.name,

                        'hsn': hsn,

                        'uom': product.uom_id.name or '',

                        'promo': '',
                        'customer_note': '',

                        'colour': colour,
                        'aging': aging,
                        'fit': fit,
                        'design': design,
                        'brand': brand,
                        'size': size,

                        'barcode': barcode,
                        'serial': serial,

                        # Exchange Qty
                        'bill_qty': exchange_qty,

                        'mrp': 0.0,

                        # Exchange RSP
                        'rsp_amount': exchange_rsp,

                        # Tax %
                        'tax_persent': tax_persent,

                        # Exchange Tax
                        'tax_amount': exchange_tax_amount,

                        # Sale Amount
                        'sale_amount': 0.0,

                        # Exchange Net
                        'net_amount': exchange_net_amount,

                        # Exchange Discount
                        'discount': exchange_discount,

                        # Exchange Total Reward Discount
                        'total_reward_discount': exchange_reward_discount,

                        # Exchange Subtotal
                        'price_subtotal': exchange_subtotal,

                        'config_id': picking_config_id,
                        'cashier_id': False,

                        # Picking reference
                        'nhcl_bill_receipt': (
                            picking.nhcl_pos_order.pos_reference
                            if picking.nhcl_pos_order
                            else ''
                        ),

                        'nhcl_date_order': picking.date_done,

                        'nhcl_company_id': store.nhcl_company_id.id,

                        'nhcl_daily_sale_detailed_report_id': self.id,

                        'employee_id': employee_id,
                        'badge_id': badge_id,
                        'from_date': store.from_date,
                        'to_date': store.to_date,

                    })

            # =========================================================
            # CREATE ALL REPORT LINES
            # =========================================================

            if report_vals:
                self.env[
                    'nhcl.daily.sale.detailed.report.line'
                ].create(report_vals)

        # =============================================================
        # OPEN REPORT
        # =============================================================

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Sale Detailed Report',
            'res_model': 'nhcl.daily.sale.detailed.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                (
                    'nhcl_daily_sale_detailed_report_id',
                    '=',
                    self.id
                )
            ],
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
    bill_qty = fields.Float(string="Quantity")
    mrp = fields.Float(string="MRP")
    tax_persent = fields.Char(string="Tax Persent")
    tax_amount = fields.Float(string="Tax Amount")
    sale_amount = fields.Float(string="Sale Value")
    rsp_amount = fields.Float(string="RSP")
    net_amount = fields.Float(string="Amount Total (Tax Incl)")
    price_subtotal = fields.Float(string="Amount Total (Tax Excl)")
    nhcl_date_order = fields.Datetime(string="Date")
    uom = fields.Char(string="UOM")
    discount = fields.Float(string="Manual Disc Amt")
    promo = fields.Char(string="Promo")
    customer_note = fields.Char(string="Customer Note")
    employee_id = fields.Many2one('hr.employee', string='Employee')
    badge_id = fields.Char(string='Badge ID')
    total_reward_discount = fields.Float(string="Promo Disc Amt")
    from_date = fields.Datetime(
        string="From Date"
    )

    to_date = fields.Datetime(
        string="To Date"
    )