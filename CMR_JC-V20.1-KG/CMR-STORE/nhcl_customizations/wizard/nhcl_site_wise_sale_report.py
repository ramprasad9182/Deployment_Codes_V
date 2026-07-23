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


class NhclPOSSaleReport(models.Model):
    _name = 'nhcl.pos.sale.report'
    _description = "nhcl pos sale report"
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
    nhcl_pos_sale_report_ids = fields.One2many('nhcl.pos.sale.report.line', 'nhcl_pos_sale_report_id')
    name = fields.Char(string='Name', default='POS Hourly Sale Report')

    # def get_pos_order_sale_report(self):
    #     self.nhcl_pos_sale_report_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     pos_lines = self.env['pos.order.line'].search([
    #         ('order_id.date_order', '>=', from_date),
    #         ('order_id.date_order', '<=', to_date),
    #     ])
    #
    #     total_amount = sum(pos_lines.mapped('price_subtotal'))
    #     total_amount_incl_tax = sum(pos_lines.mapped('price_subtotal_incl'))
    #     total_quantity_with_service = sum(pos_lines.mapped('qty'))
    #     qty_lines = pos_lines.filtered(
    #         lambda l: l.product_id.detailed_type != 'service'
    #     )
    #     total_quantity_without_service = sum(qty_lines.mapped('qty'))
    #
    #
    #     self.env['nhcl.pos.sale.report.line'].create({
    #         'nhcl_pos_sale_report_id': self.id,
    #         'nhcl_company_id': self.nhcl_company_id.id,
    #         'nhcl_amount_total': total_amount,
    #         'nhcl_amount_incl_tax_total': total_amount_incl_tax,
    #         'nhcl_quantity': total_quantity_with_service,
    #         'nhcl_total_quantity': total_quantity_without_service,
    #     })
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'POS Hourly sale Report',
    #         'res_model': 'nhcl.pos.sale.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_pos_sale_report_id', '=', self.id)],
    #         'context': {
    #             'default_nhcl_pos_sale_report_id': self.id
    #         }
    #     }

    # def get_pos_order_sale_report(self):
    #     self.nhcl_pos_sale_report_ids.unlink()
    #
    #     user_tz = self.env.user.tz or 'UTC'
    #     local = pytz.timezone(user_tz)
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     for store in self:
    #
    #         # Search POS order lines from local database
    #         pos_lines = self.env['pos.order.line'].search([
    #             ('order_id.date_order', '>=', from_date),
    #             ('order_id.date_order', '<=', to_date),
    #         ])
    #
    #         total_amount = 0.0
    #         total_amount_incl_tax = 0.0
    #         quantity = 0.0
    #
    #         for line in pos_lines:
    #             total_amount += line.price_subtotal
    #             total_amount_incl_tax += line.price_subtotal_incl
    #             quantity += line.qty
    #
    #         if total_amount > 0:
    #
    #             existing_line = self.nhcl_pos_sale_report_ids.filtered(
    #                 lambda l: l.nhcl_company_id.id == store.nhcl_company_id.id
    #             )
    #
    #             if existing_line:
    #                 existing_line.write({
    #                     'nhcl_amount_total': existing_line.nhcl_amount_total + total_amount,
    #                     'nhcl_amount_incl_tax_total': existing_line.nhcl_amount_incl_tax_total + total_amount_incl_tax,
    #                     'nhcl_quantity': existing_line.nhcl_quantity + quantity
    #                 })
    #             else:
    #                 self.env['nhcl.pos.sale.report.line'].create({
    #                     'nhcl_pos_sale_report_id': self.id,
    #                     'nhcl_company_id': store.nhcl_company_id.id,
    #                     'nhcl_amount_total': total_amount,
    #                     'nhcl_amount_incl_tax_total': total_amount_incl_tax,
    #                     'nhcl_quantity': quantity
    #                 })
    def get_pos_order_sale_report(self):
        self.nhcl_pos_sale_report_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        domain = [
            ('order_id.date_order', '>=', from_date),
            ('order_id.date_order', '<=', to_date),
        ]

        # --- Amount totals (SQL aggregation) ---
        amount_data = self.env['pos.order.line'].search_read(
            domain,
            ['price_subtotal', 'price_subtotal_incl', 'qty', 'product_id'],
        )

        total_amount = sum(d['price_subtotal'] for d in amount_data)
        total_amount_incl_tax = sum(d['price_subtotal_incl'] for d in amount_data)
        total_quantity_with_service = sum(d['qty'] for d in amount_data)

        # --- Get service product ids once ---
        service_products = set(
            self.env['product.product'].search([
                ('detailed_type', '=', 'service')
            ]).ids
        )

        # --- Qty without service ---
        total_quantity_without_service = sum(
            d['qty'] for d in amount_data
            if d['product_id'] and d['product_id'][0] not in service_products
        )

        self.env['nhcl.pos.sale.report.line'].create({
            'nhcl_pos_sale_report_id': self.id,
            'nhcl_company_id': self.nhcl_company_id.id,
            'nhcl_amount_total': total_amount,
            'nhcl_amount_incl_tax_total': total_amount_incl_tax,
            'nhcl_quantity': total_quantity_with_service,
            'nhcl_total_quantity': total_quantity_without_service,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Hourly sale Report',
            'res_model': 'nhcl.pos.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_sale_report_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_sale_report_id': self.id
            }
        }
    def action_to_reset(self):
        self.nhcl_company_id = False
        self.from_date = False
        self.to_date = False
        self.nhcl_pos_sale_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Company','Total Amount ', 'Total Amount INCL Tax','Quantity']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_sale_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_store_id.nhcl_store_name.name)
            worksheet.write(row_num, 1, line.nhcl_amount_total)
            worksheet.write(row_num, 2, line.nhcl_amount_incl_tax_total)
            worksheet.write(row_num, 3, line.nhcl_quantity)

        workbook.close()

        # Get the content of the buffer
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # Encode the data in base64
        encoded_data = base64.b64encode(excel_data)

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Site_wise_total_sale_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Site_wise_Sale_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_pos_sale_detailed_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Hourly sale Report',
            'res_model': 'nhcl.pos.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_sale_report_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_sale_report_id': self.id
            }
        }


class NhclPOSsaleReportLine(models.Model):
    _name = 'nhcl.pos.sale.report.line'
    _description = "nhcl pos sale report line"

    nhcl_pos_sale_report_id = fields.Many2one('nhcl.pos.sale.report', string="Pos Sale Report")
    nhcl_amount_total = fields.Float(string="Amount Total")
    nhcl_amount_incl_tax_total = fields.Float(string="Total Amount INCl Tax")
    nhcl_quantity = fields.Integer(string="Quantity")
    nhcl_total_quantity = fields.Integer(string="Quantity(Excl.Disc)")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
