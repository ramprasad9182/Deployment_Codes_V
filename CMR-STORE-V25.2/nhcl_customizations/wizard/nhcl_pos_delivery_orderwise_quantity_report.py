from odoo import models,fields,api,_
import requests
from datetime import datetime, time, timedelta
import pytz

from odoo.addons.test_new_api.models.test_new_api import Move
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class NhclPOSDeliveryHourReport(models.Model):
    _name = 'nhcl.pos.delivery.hour.report'
    _description = "nhcl pos delivery order hour report"
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
    nhcl_pos_delivery_order_hour_report_ids = fields.One2many('nhcl.pos.delivery.order.hour.report.line', 'nhcl_pos_delivery_order_hour_report_id')
    name = fields.Char(string='Name', default='POS Delivery Based on Quantity Report')



    # def get_pos_delivery_order_hour_report(self):
    #     self.nhcl_pos_delivery_order_hour_report_ids.unlink()
    #
    #     from_dt = fields.Datetime.to_datetime(self.from_date)
    #     to_dt = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         domain = [
    #             ('create_date', '>=', from_dt),
    #             ('create_date', '<=', to_dt),
    #             ('picking_id.picking_type_id.name', '=', 'PoS Orders'),
    #             ('state', '=', 'done')
    #         ]
    #
    #         stock_moves = self.env['stock.move.line'].search(domain)
    #
    #         lines_to_create = []
    #
    #         for move in stock_moves:
    #             product = move.product_id
    #             if not product:
    #                 continue
    #
    #             date_order = fields.Datetime.context_timestamp(self, move.create_date)
    #
    #             lines_to_create.append({
    #                 'nhcl_product_id': product.display_name,
    #                 'nhcl_serial': move.lot_id.name or '',
    #                 'nhcl_product_barcode': move.lot_id.ref or '',
    #                 'nhcl_name': move.picking_id.name or '',
    #                 'nhcl_order_quantity': move.quantity,
    #                 # 'nhcl_date_order': date_order.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    #                 'nhcl_date_order': move.create_date,
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'nhcl_pos_delivery_order_hour_report_id': self.id,
    #                 'from_date': store.from_date,
    #                 'to_date': store.to_date,
    #             })
    #
    #         # single create instead of thousands
    #         if lines_to_create:
    #             self.env['nhcl.pos.delivery.order.hour.report.line'].create(lines_to_create)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'POS Delivery Based on Quantity Report',
    #         'res_model': 'nhcl.pos.delivery.order.hour.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_pos_delivery_order_hour_report_id', '=', self.id)],
    #         'context': {
    #                         'default_nhcl_pos_delivery_order_hour_report_id': self.id
    #                     }
    #     }

    def get_pos_delivery_order_hour_report(self):
        self.nhcl_pos_delivery_order_hour_report_ids.unlink()

        from_dt = fields.Datetime.to_datetime(self.from_date)
        to_dt = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            # ---------------------------------------------------------
            # NORMAL POS DELIVERY STOCK MOVE LINES
            # ---------------------------------------------------------

            domain = [
                ('create_date', '>=', from_dt),
                ('create_date', '<=', to_dt),
                ('picking_id.picking_type_id.name', '=', 'PoS Orders'),
                ('state', '=', 'done')
            ]

            stock_moves = self.env['stock.move.line'].search(domain)

            lines_to_create = []

            # ---------------------------------------------------------
            # NORMAL POS DELIVERY LINES
            # ---------------------------------------------------------

            for move in stock_moves:

                product = move.product_id

                if not product:
                    continue

                lines_to_create.append({
                    'nhcl_product_id': product.display_name,
                    'nhcl_serial': move.lot_id.name or '',
                    'nhcl_product_barcode': move.lot_id.ref or '',
                    'nhcl_name': move.picking_id.name or '',

                    # Normal delivery quantity = POS quantity
                    'nhcl_order_quantity': move.quantity,

                    'nhcl_date_order': move.create_date,

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'nhcl_pos_delivery_order_hour_report_id': self.id,

                    'from_date': store.from_date,
                    'to_date': store.to_date,
                })

            # ---------------------------------------------------------
            # EXCHANGE STOCK MOVES
            # nhcl_exchange = True on stock.move
            # ---------------------------------------------------------

            exchange_domain = [
                ('create_date', '>=', from_dt),
                ('create_date', '<=', to_dt),
                ('state', '=', 'done'),
                ('nhcl_exchange', '=', True),
            ]

            exchange_moves = self.env['stock.move'].search(
                exchange_domain
            )

            # ---------------------------------------------------------
            # EXCHANGE LINES
            # Directly use stock.move quantity
            # Exchange quantity should be NEGATIVE
            # ---------------------------------------------------------

            for exchange_move in exchange_moves:

                product = exchange_move.product_id

                if not product:
                    continue

                lines_to_create.append({
                    'nhcl_product_id': product.display_name,

                    # Exchange move generally may not have lot/ref
                    'nhcl_serial': (
                        exchange_move.move_line_ids[:1].lot_id.name
                        if exchange_move.move_line_ids
                        else ''
                    ),

                    'nhcl_product_barcode': (
                        exchange_move.move_line_ids[:1].lot_id.ref
                        if exchange_move.move_line_ids
                        else ''
                    ),

                    'nhcl_name': (
                            exchange_move.picking_id.name or ''
                    ),

                    # IMPORTANT:
                    # Exchange quantity is negative
                    'nhcl_order_quantity': -abs(
                        exchange_move.product_uom_qty
                    ),

                    'nhcl_date_order': exchange_move.create_date,

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'nhcl_pos_delivery_order_hour_report_id': self.id,

                    'from_date': store.from_date,
                    'to_date': store.to_date,
                })

            # ---------------------------------------------------------
            # CREATE ALL REPORT LINES
            # ---------------------------------------------------------

            if lines_to_create:
                self.env[
                    'nhcl.pos.delivery.order.hour.report.line'
                ].create(lines_to_create)

        # -------------------------------------------------------------
        # OPEN REPORT
        # -------------------------------------------------------------

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Delivery Based on Quantity Report',
            'res_model': 'nhcl.pos.delivery.order.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                (
                    'nhcl_pos_delivery_order_hour_report_id',
                    '=',
                    self.id
                )
            ],
            'context': {
                'default_nhcl_pos_delivery_order_hour_report_id': self.id
            }
        }


    def action_to_reset(self):
        self.write({
            'nhcl_company_id' : False,
            'from_date' : False,
            'to_date' : False
        })
        self.nhcl_pos_delivery_order_hour_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Company','Product', 'Date','Quantity']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_delivery_order_hour_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_store_id.nhcl_store_name.name)
            worksheet.write(row_num, 1, line.nhcl_product_id)
            worksheet.write(row_num, 2, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 3, line.nhcl_order_quantity)

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
            'name': f'POS_Delivery_orders_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Delivery_orders_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_pos_delivery_order_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Delivery Order Hour Report Lines',
            'res_model': 'nhcl.pos.delivery.order.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_delivery_order_hour_report_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_delivery_order_hour_report_id': self.id
            }
        }


class NhclPOSHourReportLine(models.Model):
    _name = 'nhcl.pos.delivery.order.hour.report.line'
    _description = "nhcl pos delivery order hour report line"

    from_date = fields.Datetime(string="From Date")
    to_date = fields.Datetime(string="To Date")
    nhcl_pos_delivery_order_hour_report_id = fields.Many2one('nhcl.pos.delivery.hour.report', string="Pos Hour Report")
    nhcl_name = fields.Char(string="Name")
    nhcl_product_id = fields.Char(string="Product")
    nhcl_date_order = fields.Datetime(string="Order Date")
    nhcl_order_quantity = fields.Float(string="Quantity",digits='Product Unit of Measure')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    nhcl_serial = fields.Char(string="Serial No")
    nhcl_product_barcode = fields.Char(string="Barcode")

