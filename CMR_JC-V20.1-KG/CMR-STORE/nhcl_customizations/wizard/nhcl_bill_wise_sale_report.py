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


class NhclPOSHourReport(models.Model):
    _name = 'nhcl.pos.hour.report'
    _description = "nhcl pos hour report"
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
    nhcl_pos_hour_report_ids = fields.One2many('nhcl.pos.hour.report.line', 'nhcl_pos_hour_report_id')
    name = fields.Char(string='Name', default='Bill Wise Sale Report')
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Quantities')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Amount Total Excl Tax')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    total_in_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Amount Total Incl Tax')
    total_amount_payment = fields.Float(compute="_compute_nhcl_show_totals", string='Paid Total')
    config_id = fields.Many2one('pos.config', string='Terminal')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_pos_hour_report_ids
            rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            rec.total_discount_amount = sum(lines.mapped('nhcl_discount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_in_amount_total = sum(lines.mapped('nhcl_in_amount_total'))
            rec.total_amount_payment = sum(lines.mapped('nhcl_amount_payment'))

    def get_pos_order_hour_report(self):
        # Remove existing lines
        self.nhcl_pos_hour_report_ids.unlink()

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id)
            ]

            # Filter by terminal if selected
            if store.config_id:
                domain.append(
                    ('order_id.config_id', '=', store.config_id.id)
                )

            # Fetch POS order lines
            pos_lines = self.env['pos.order.line'].search(domain)

            grouped_data = {}

            for line in pos_lines:
                order = line.order_id
                order_ref = order.name
                receipt_ref = order.pos_reference
                terminal_name = order.config_id.id
                order_discount = order.amount_discount or 0.0
                order_reward_discount = order.amount_reward_discount or 0.0

                if not order_ref:
                    continue

                # Convert order date to user timezone
                date_order = fields.Datetime.context_timestamp(
                    self, order.date_order
                )

                qty = line.qty
                subtotal = line.price_subtotal
                tax_inc_total = line.price_subtotal_incl
                is_reward = getattr(line, 'is_reward_line', False)

                # Ignore refund lines
                # if qty < 0:
                #     continue

                if order_ref not in grouped_data:
                    grouped_data[order_ref] = {
                        'qty': 0,
                        'amount_excl': 0.0,
                        'amount_incl': 0.0,
                        'payment': 0.0,
                        'tax_amount': 0.0,
                        'nhcl_discount': order_discount,
                        'nhcl_reward_discount': order_reward_discount,
                        'date': line.order_id.date_order,
                        'receipt_ref': receipt_ref,
                        'terminal_name': terminal_name,
                    }

                # Sales lines
                if subtotal > 0:
                    grouped_data[order_ref]['qty'] += qty
                    grouped_data[order_ref]['amount_excl'] += subtotal
                    grouped_data[order_ref]['amount_incl'] += tax_inc_total
                    grouped_data[order_ref]['payment'] += tax_inc_total
                    grouped_data[order_ref]['tax_amount'] += (
                            tax_inc_total - subtotal
                    )

                # Discount lines
                elif is_reward or subtotal < 0:
                    grouped_data[order_ref]['payment'] += tax_inc_total

            vals_list = []
            for order_ref, values in grouped_data.items():
                vals_list.append({
                    'nhcl_order_ref': order_ref,
                    'nhcl_bill_receipt_no': values['receipt_ref'],
                    'nhcl_order_quantity': values['qty'],
                    'nhcl_amount_total': values['amount_excl'],
                    'nhcl_in_amount_total': values['amount_incl'],
                    'nhcl_amount_payment': values['payment'],
                    'nhcl_tax_amount': values['tax_amount'],
                    'nhcl_discount': values['nhcl_discount'],
                    'nhcl_reward_discount': values['nhcl_reward_discount'],
                    'nhcl_date_order': values['date'],
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'config_id': values['terminal_name'],
                    'nhcl_pos_hour_report_id': self.id,
                })

            if vals_list:
                self.env['nhcl.pos.hour.report.line'].create(vals_list)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bill Wise Sale Report Lines',
            'res_model': 'nhcl.pos.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hour_report_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hour_report_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_pos_hour_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Company','Shop Name', 'POS Date','Quantity','Total Amount ']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_hour_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_store_id.nhcl_store_name.name)
            worksheet.write(row_num, 1, line.nhcl_order_ref)
            worksheet.write(row_num, 2, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 3, line.nhcl_order_quantity)
            worksheet.write(row_num, 4, line.nhcl_amount_total)

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
            'name': f'POS_Order_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Order_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_pos_hour_lines(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Hour Report Lines',
            'res_model': 'nhcl.pos.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hour_report_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hour_report_id': self.id
            }
        }

    def job_status_log(self):

        # Delete old dashboard records
        self.env['nhcl.initiated.status.dashboard.log'].search([]).unlink()

        # Required job names
        job_names = [
            'Missing Serial Number Transaction',
            'POS Order Live Sync'
        ]

        dashboard_vals = []

        for job in job_names:

            # Get latest record for each job
            latest_record = self.env['nhcl.initiated.status.log'].search(
                [('nhcl_job_name', '=', job)],
                order='nhcl_date_of_log desc',
                limit=1
            )

            if latest_record:
                dashboard_vals.append({
                    'nhcl_serial_no': latest_record.nhcl_serial_no,
                    'nhcl_date_of_log': latest_record.nhcl_date_of_log,
                    'nhcl_job_name': latest_record.nhcl_job_name,
                    'nhcl_status': latest_record.nhcl_status,
                    'nhcl_details_status': latest_record.nhcl_details_status,
                })

        # Create dashboard records
        if dashboard_vals:
            self.env['nhcl.initiated.status.dashboard.log'].create(dashboard_vals)

        # Return action
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Initiated Status Dashboard',
            'res_model': 'nhcl.initiated.status.dashboard.log',
            'view_mode': 'tree',
            'target': 'current',
        }

class NhclPOSHourReportLine(models.Model):
    _name = 'nhcl.pos.hour.report.line'
    _description = "nhcl pos hour report line"

    nhcl_pos_hour_report_id = fields.Many2one('nhcl.pos.hour.report', string="Pos Hour Report")
    nhcl_order_ref = fields.Char(string="Order Ref No")
    nhcl_date_order = fields.Datetime(string="Order Date")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_amount_total = fields.Float(string="Amount Total Exc Tax")
    nhcl_in_amount_total = fields.Float(string="Amount Total Inc Tax")
    nhcl_amount_paid = fields.Datetime(string="Amount Paid Time")
    nhcl_amount_payment = fields.Float(string="Amount Paid")
    nhcl_tax_amount = fields.Float(string="Tax Amount")
    nhcl_discount_amount = fields.Float(string="Discount Amount")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    nhcl_bill_receipt_no = fields.Char(string="Bill Receipt No")
    config_id = fields.Many2one('pos.config', string='Terminal')
    nhcl_discount = fields.Float(string="Manual Discount Amount")
    nhcl_reward_discount = fields.Float(string="Promo Discount Amount")
