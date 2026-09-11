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


class NhclPOSSaleReport(models.Model):
    _name = 'nhcl.pos.sale.report'
    _description = "nhcl pos sale report"
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
    nhcl_pos_sale_report_ids = fields.One2many('nhcl.pos.sale.report.line', 'nhcl_pos_sale_report_id')
    name = fields.Char(string='Name', default='POS Hourly Sale Report')



    # def get_pos_order_sale_report(self):
    #     self.nhcl_pos_sale_report_ids.unlink()
    #
    #     from_date = fields.Datetime.to_datetime(self.from_date)
    #     to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #     domain = [
    #         ('order_id.date_order', '>=', from_date),
    #         ('order_id.date_order', '<=', to_date),
    #         ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
    #     ]
    #
    #     # --- Amount totals (SQL aggregation) ---
    #     amount_data = self.env['pos.order.line'].search_read(
    #         domain,
    #         ['price_subtotal', 'price_subtotal_incl', 'qty', 'product_id'],
    #     )
    #
    #     total_amount = sum(d['price_subtotal'] for d in amount_data)
    #     # total_amount_incl_tax = sum(d['price_subtotal_incl'] for d in amount_data)
    #     total_quantity_with_service = sum(d['qty'] for d in amount_data)
    #
    #
    #     order_domain = [
    #         ('date_order', '>=', from_date),
    #         ('date_order', '<=', to_date),
    #         ('state', 'in', ['paid', 'done', 'invoiced']),
    #     ]
    #     orders = self.env['pos.order'].search(order_domain)
    #     total_amount_paid = sum(orders.mapped('amount_paid'))
    #
    #     # --- Get service product ids once ---
    #     service_products = set(
    #         self.env['product.product'].search([
    #             ('detailed_type', '=', 'service')
    #         ]).ids
    #     )
    #
    #     # --- Qty without service ---
    #     total_quantity_without_service = sum(
    #         d['qty'] for d in amount_data
    #         if d['product_id'] and d['product_id'][0] not in service_products
    #     )
    #
    #     self.env['nhcl.pos.sale.report.line'].create({
    #         'nhcl_pos_sale_report_id': self.id,
    #         'nhcl_company_id': self.nhcl_company_id.id,
    #         'nhcl_amount_total': total_amount,
    #         # 'nhcl_amount_incl_tax_total': total_amount_incl_tax,
    #         'nhcl_amount_incl_tax_total': total_amount_paid,
    #         'nhcl_quantity': total_quantity_with_service,
    #         'nhcl_total_quantity': total_quantity_without_service,
    #         'from_date': self.from_date,
    #         'to_date': self.to_date,
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

    def get_pos_order_sale_report(self):
        self.nhcl_pos_sale_report_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        # ---------------------------------------------------------
        # NORMAL POS SALE LINES
        # ---------------------------------------------------------

        domain = [
            ('order_id.date_order', '>=', from_date),
            ('order_id.date_order', '<=', to_date),
            ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
        ]

        amount_data = self.env['pos.order.line'].search_read(
            domain,
            [
                'price_subtotal',
                'price_subtotal_incl',
                'qty',
                'product_id'
            ],
        )

        # ---------------------------------------------------------
        # NORMAL POS TOTALS
        # ---------------------------------------------------------

        total_amount = sum(
            d['price_subtotal'] for d in amount_data
        )

        total_quantity_with_service = sum(
            d['qty'] for d in amount_data
        )

        # ---------------------------------------------------------
        # POS ORDERS
        # ---------------------------------------------------------

        order_domain = [
            ('date_order', '>=', from_date),
            ('date_order', '<=', to_date),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ]

        orders = self.env['pos.order'].search(order_domain)

        total_amount_paid = sum(
            orders.mapped('amount_paid')
        )

        # ---------------------------------------------------------
        # SERVICE PRODUCTS
        # ---------------------------------------------------------

        service_products = set(
            self.env['product.product'].search([
                ('detailed_type', '=', 'service')
            ]).ids
        )

        # ---------------------------------------------------------
        # NORMAL STORABLE / NON-SERVICE QUANTITY
        # ---------------------------------------------------------

        total_quantity_without_service = sum(
            d['qty']
            for d in amount_data
            if d['product_id']
            and d['product_id'][0] not in service_products
        )

        # =========================================================
        # EXCHANGE
        # =========================================================

        exchange_moves = self.env['stock.move'].search([
            ('create_date', '>=', from_date),
            ('create_date', '<=', to_date),
            ('state', '=', 'done'),
            ('nhcl_exchange', '=', True),
        ])

        # ---------------------------------------------------------
        # EXCHANGE TOTALS
        # ---------------------------------------------------------

        exchange_amount_subtotal = sum(
            exchange_moves.mapped('nhcl_price_subtotal')
        )

        exchange_quantity = sum(
            exchange_moves.mapped('quantity')
        )

        exchange_amount_total = sum(
            exchange_moves.mapped('nhcl_price_total')
        )

        # ---------------------------------------------------------
        # ADD EXCHANGE AS NEGATIVE
        # ---------------------------------------------------------

        total_amount -= exchange_amount_subtotal

        total_quantity_without_service -= exchange_quantity

        total_amount_paid -= exchange_amount_total

        # =========================================================
        # CREATE REPORT LINE
        # =========================================================

        self.env['nhcl.pos.sale.report.line'].create({
            'nhcl_pos_sale_report_id': self.id,

            'nhcl_company_id': self.nhcl_company_id.id,

            # Normal POS amount
            # - Exchange subtotal
            'nhcl_amount_total': total_amount,

            # Normal POS amount paid
            # - Exchange total amount
            'nhcl_amount_incl_tax_total': total_amount_paid,

            # ALL POS quantities including service
            'nhcl_quantity': total_quantity_with_service,

            # Normal storable/non-service qty
            # - Exchange qty
            'nhcl_total_quantity': total_quantity_without_service,

            'from_date': self.from_date,
            'to_date': self.to_date,
        })

        # ---------------------------------------------------------
        # OPEN REPORT
        # ---------------------------------------------------------

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Hourly sale Report',
            'res_model': 'nhcl.pos.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                ('nhcl_pos_sale_report_id', '=', self.id)
            ],
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
    nhcl_amount_total = fields.Float(string="Amount Total(Excl Tax)")
    nhcl_amount_incl_tax_total = fields.Float(string="Amount Total (Incl Tax)")
    nhcl_quantity = fields.Float(string="Quantity(Incl Service Products)", digits='Product Unit of Measure')
    nhcl_total_quantity = fields.Float(string="Quantity", digits='Product Unit of Measure')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    from_date = fields.Datetime(string="From Date")
    to_date = fields.Datetime(string="To Date")