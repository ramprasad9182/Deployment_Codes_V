from odoo import models,fields,api,_
import requests
from datetime import datetime, time
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
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    nhcl_pos_delivery_order_hour_report_ids = fields.One2many('nhcl.pos.delivery.order.hour.report.line', 'nhcl_pos_delivery_order_hour_report_id')
    name = fields.Char(string='Name', default='POS Delivery Based on Quantity Report')

    # def get_pos_delivery_order_hour_report(self):
    #     self.nhcl_pos_delivery_order_hour_report_ids.unlink()
    #
    #     user_tz = self.env.user.tz or 'UTC'
    #     local_tz = pytz.timezone(user_tz)
    #
    #     # Convert date range
    #     from_dt = fields.Datetime.to_datetime(self.from_date)
    #     to_dt = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         # Search stock moves directly from Odoo
    #         stock_moves = self.env['stock.move.line'].search([
    #             ('create_date', '>=', from_dt),
    #             ('create_date', '<=', to_dt),
    #             ('picking_type_id.name', '=', 'PoS Orders')
    #         ])
    #
    #         for move in stock_moves:
    #
    #             product = move.product_id
    #             if not product:
    #                 continue
    #
    #             date_order = fields.Datetime.context_timestamp(self, move.create_date)
    #
    #             if from_dt <= move.create_date <= to_dt:
    #                 self.env['nhcl.pos.delivery.order.hour.report.line'].create({
    #                     'nhcl_product_id': product.display_name,
    #                     'nhcl_serial': move.lot_id.name if move.lot_id.name else '',
    #                     'nhcl_product_barcode': move.lot_id.ref if move.lot_id.ref else '',
    #                     'nhcl_name': move.picking_id.name if move.picking_id else '',
    #                     'nhcl_order_quantity': move.quantity,
    #                     'nhcl_date_order': date_order.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    #                     'nhcl_company_id': store.nhcl_company_id.id,
    #                     'nhcl_pos_delivery_order_hour_report_id': self.id
    #                 })
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'POS Delivery Based on Quantity Lines',
    #         'res_model': 'nhcl.pos.delivery.order.hour.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_pos_delivery_order_hour_report_id', '=', self.id)],
    #         'context': {
    #             'default_nhcl_pos_delivery_order_hour_report_id': self.id
    #         }
    #     }

    def get_pos_delivery_order_hour_report(self):
        self.nhcl_pos_delivery_order_hour_report_ids.unlink()

        from_dt = fields.Datetime.to_datetime(self.from_date)
        to_dt = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            domain = [
                ('create_date', '>=', from_dt),
                ('create_date', '<=', to_dt),
                ('picking_id.picking_type_id.name', '=', 'PoS Orders'),
            ]

            stock_moves = self.env['stock.move.line'].search(domain)

            lines_to_create = []

            for move in stock_moves:
                product = move.product_id
                if not product:
                    continue

                date_order = fields.Datetime.context_timestamp(self, move.create_date)

                lines_to_create.append({
                    'nhcl_product_id': product.display_name,
                    'nhcl_serial': move.lot_id.name or '',
                    'nhcl_product_barcode': move.lot_id.ref or '',
                    'nhcl_name': move.picking_id.name or '',
                    'nhcl_order_quantity': move.quantity,
                    'nhcl_date_order': date_order.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'nhcl_pos_delivery_order_hour_report_id': self.id
                })

            # single create instead of thousands
            if lines_to_create:
                self.env['nhcl.pos.delivery.order.hour.report.line'].create(lines_to_create)

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Delivery Based on Quantity Report',
            'res_model': 'nhcl.pos.delivery.order.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_delivery_order_hour_report_id', '=', self.id)],
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

    nhcl_pos_delivery_order_hour_report_id = fields.Many2one('nhcl.pos.delivery.hour.report', string="Pos Hour Report")
    nhcl_name = fields.Char(string="Name")
    nhcl_product_id = fields.Char(string="Product")
    nhcl_date_order = fields.Datetime(string="Order Date")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    nhcl_serial = fields.Char(string="Serial No")
    nhcl_product_barcode = fields.Char(string="Barcode")


