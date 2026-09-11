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


class NhclPOSHourReport(models.Model):
    _name = 'nhcl.pos.hour.report'
    _description = "nhcl pos hour report"
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
    #old
    # def get_pos_order_hour_report(self):
    #     # Remove existing lines
    #     self.nhcl_pos_hour_report_ids.unlink()
    #
    #     user_tz = self.env.user.tz or 'UTC'
    #     local_tz = pytz.timezone(user_tz)
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
    #
    #
    #         # Filter by terminal if selected
    #         if store.config_id:
    #             domain.append(
    #                 ('order_id.config_id', '=', store.config_id.id)
    #             )
    #
    #         # Fetch POS order lines
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         grouped_data = {}
    #
    #         for line in pos_lines:
    #             order = line.order_id
    #             order_ref = order.name
    #             receipt_ref = order.pos_reference
    #             terminal_name = order.config_id.id
    #             order_discount = order.amount_discount or 0.0
    #             order_reward_discount = order.amount_reward_discount or 0.0
    #
    #             if not order_ref:
    #                 continue
    #
    #             # Convert order date to user timezone
    #             date_order = fields.Datetime.context_timestamp(
    #                 self, order.date_order
    #             )
    #
    #             qty = line.qty
    #             subtotal = line.price_subtotal
    #             tax_inc_total = line.price_subtotal_incl
    #             is_reward = getattr(line, 'is_reward_line', False)
    #             calculated_tax_amount = tax_inc_total - subtotal
    #
    #             # Ignore refund lines
    #             # if qty < 0:
    #             #     continue
    #
    #             if receipt_ref not in grouped_data:
    #                 grouped_data[receipt_ref] = {
    #                     'qty': 0,
    #                     'amount_excl': 0.0,
    #                     'amount_incl': 0.0,
    #                     # 'payment': 0.0,
    #                     'payment':  order.amount_paid or 0.0,
    #                     # 'tax_amount': 0.0,
    #                     'tax_amount': order.amount_tax or 0.0,
    #                     'nhcl_discount': order_discount,
    #                     'nhcl_reward_discount': order_reward_discount,
    #                     'date': line.order_id.date_order,
    #                     'receipt_ref': receipt_ref,
    #                     'terminal_name': terminal_name,
    #                     'order_ref': order_ref,
    #                     'calculated_tax_amount': 0.0,
    #                 }
    #
    #             # Sales lines
    #             # if subtotal > 0:
    #             grouped_data[receipt_ref]['qty'] += qty
    #             grouped_data[receipt_ref]['amount_excl'] += subtotal
    #             grouped_data[receipt_ref]['amount_incl'] += tax_inc_total
    #             grouped_data[receipt_ref]['calculated_tax_amount'] += calculated_tax_amount
    #             # grouped_data[order_ref]['payment'] += tax_inc_total
    #             # grouped_data[order_ref]['tax_amount'] += (
    #             #         tax_inc_total - subtotal
    #             # )
    #
    #         # Discount lines
    #         # elif is_reward or subtotal < 0:
    #         #     grouped_data[order_ref]['payment'] += tax_inc_total
    #
    #         vals_list = []
    #         for receipt_ref, values in grouped_data.items():
    #             vals_list.append({
    #                 'nhcl_order_ref': values['order_ref'],
    #                 'nhcl_bill_receipt_no': values['receipt_ref'],
    #                 'nhcl_order_quantity': values['qty'],
    #                 'nhcl_amount_total': values['amount_excl'],
    #                 'nhcl_in_amount_total': values['amount_incl'],
    #                 'nhcl_amount_payment': values['payment'],
    #                 'nhcl_tax_amount': values['tax_amount'],
    #                 'nhcl_discount': values['nhcl_discount'],
    #                 'nhcl_reward_discount': values['nhcl_reward_discount'],
    #                 'nhcl_date_order': values['date'],
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'config_id': values['terminal_name'],
    #                 'nhcl_pos_hour_report_id': self.id,
    #                 'nhcl_calculated_tax_amount': values['calculated_tax_amount'],
    #             })
    #
    #         if vals_list:
    #             self.env['nhcl.pos.hour.report.line'].create(vals_list)
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Bill Wise Sale Report Lines',
    #         'res_model': 'nhcl.pos.hour.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [('nhcl_pos_hour_report_id', '=', self.id)],
    #         'context': {
    #             'default_nhcl_pos_hour_report_id': self.id
    #         }
    #     }

    ##########below correct

    # def get_pos_order_hour_report(self):
    #     # Remove existing lines
    #     self.nhcl_pos_hour_report_ids.unlink()
    #
    #     user_tz = self.env.user.tz or 'UTC'
    #     local_tz = pytz.timezone(user_tz)
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
    #         # Filter by terminal if selected
    #         if store.config_id:
    #             domain.append(
    #                 ('order_id.config_id', '=', store.config_id.id)
    #             )
    #
    #         # Fetch POS order lines
    #         pos_lines = self.env['pos.order.line'].search(domain)
    #
    #         grouped_data = {}
    #
    #         for line in pos_lines:
    #             order = line.order_id
    #             order_ref = order.name
    #             receipt_ref = order.pos_reference
    #             terminal_name = order.config_id.id
    #             order_discount = order.amount_discount or 0.0
    #             order_reward_discount = order.amount_reward_discount or 0.0
    #
    #             if not order_ref:
    #                 continue
    #
    #             # Convert order date to user timezone
    #             date_order = fields.Datetime.context_timestamp(
    #                 self, order.date_order
    #             )
    #
    #             qty = line.qty
    #             subtotal = line.price_subtotal
    #             tax_inc_total = line.price_subtotal_incl
    #             is_reward = getattr(line, 'is_reward_line', False)
    #             calculated_tax_amount = tax_inc_total - subtotal
    #
    #             # ---------------------------------------------------------
    #             # STORABLE QTY
    #             # Only detailed_type == 'product'
    #             # ---------------------------------------------------------
    #
    #             storable_qty = 0.0
    #
    #             if line.product_id.detailed_type == 'product':
    #                 storable_qty = qty
    #
    #             if receipt_ref not in grouped_data:
    #                 grouped_data[receipt_ref] = {
    #                     'qty': 0,
    #                     'storable_qty': 0,
    #                     'amount_excl': 0.0,
    #                     'amount_incl': 0.0,
    #                     'payment': order.amount_paid or 0.0,
    #                     'tax_amount': order.amount_tax or 0.0,
    #                     'nhcl_discount': order_discount,
    #                     'nhcl_reward_discount': order_reward_discount,
    #                     'date': line.order_id.date_order,
    #                     'receipt_ref': receipt_ref,
    #                     'terminal_name': terminal_name,
    #                     'order_ref': order_ref,
    #                     'calculated_tax_amount': 0.0,
    #                 }
    #
    #             # ---------------------------------------------------------
    #             # ALL TYPES QTY
    #             # ---------------------------------------------------------
    #
    #             grouped_data[receipt_ref]['qty'] += qty
    #
    #             # ---------------------------------------------------------
    #             # ONLY STORABLE QTY
    #             # ---------------------------------------------------------
    #
    #             grouped_data[receipt_ref]['storable_qty'] += storable_qty
    #
    #             # ---------------------------------------------------------
    #             # AMOUNTS
    #             # ---------------------------------------------------------
    #
    #             grouped_data[receipt_ref]['amount_excl'] += subtotal
    #             grouped_data[receipt_ref]['amount_incl'] += tax_inc_total
    #             grouped_data[receipt_ref]['calculated_tax_amount'] += (calculated_tax_amount)
    #
    #         vals_list = []
    #
    #         for receipt_ref, values in grouped_data.items():
    #             vals_list.append({
    #                 'nhcl_order_ref': values['order_ref'],
    #                 'nhcl_bill_receipt_no': values['receipt_ref'],
    #
    #                 # Existing - all types quantity
    #                 'nhcl_order_quantity': values['qty'],
    #
    #                 # New - only storable quantity
    #                 'storable_qty': values['storable_qty'],
    #
    #                 'nhcl_amount_total': values['amount_excl'],
    #                 'nhcl_in_amount_total': values['amount_incl'],
    #                 'nhcl_amount_payment': values['payment'],
    #                 'nhcl_tax_amount': values['tax_amount'],
    #                 'nhcl_discount': values['nhcl_discount'],
    #                 'nhcl_reward_discount': values['nhcl_reward_discount'],
    #                 'nhcl_date_order': values['date'],
    #                 'nhcl_company_id': store.nhcl_company_id.id,
    #                 'config_id': values['terminal_name'],
    #                 'nhcl_pos_hour_report_id': self.id,
    #                 'nhcl_calculated_tax_amount': values[
    #                     'calculated_tax_amount'
    #                 ],
    #
    #                 # New fields
    #                 'from_date': store.from_date,
    #                 'to_date': store.to_date,
    #             })
    #
    #         if vals_list:
    #             self.env['nhcl.pos.hour.report.line'].create(vals_list)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Bill Wise Sale Report Lines',
    #         'res_model': 'nhcl.pos.hour.report.line',
    #         'view_mode': 'tree,pivot',
    #         'domain': [
    #             ('nhcl_pos_hour_report_id', '=', self.id)
    #         ],
    #         'context': {
    #             'default_nhcl_pos_hour_report_id': self.id
    #         }
    #     }

    def get_pos_order_hour_report(self):
        # Remove existing lines
        self.nhcl_pos_hour_report_ids.unlink()

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            # ---------------------------------------------------------
            # NORMAL POS ORDER LINES
            # ---------------------------------------------------------

            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
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
                    self,
                    order.date_order
                )

                qty = line.qty
                subtotal = line.price_subtotal
                tax_inc_total = line.price_subtotal_incl

                is_reward = getattr(
                    line,
                    'is_reward_line',
                    False
                )

                calculated_tax_amount = (
                        tax_inc_total - subtotal
                )

                # -----------------------------------------------------
                # STORABLE QTY
                # Only detailed_type == 'product'
                # -----------------------------------------------------

                storable_qty = 0.0

                if line.product_id.detailed_type == 'product':
                    storable_qty = qty

                # -----------------------------------------------------
                # GROUP BY RECEIPT
                # -----------------------------------------------------

                if receipt_ref not in grouped_data:
                    grouped_data[receipt_ref] = {
                        'qty': 0.0,
                        'storable_qty': 0.0,
                        'amount_excl': 0.0,
                        'amount_incl': 0.0,

                        'payment': order.amount_paid or 0.0,

                        'tax_amount': order.amount_tax or 0.0,

                        'nhcl_discount': order_discount,

                        'nhcl_reward_discount': order_reward_discount,

                        'date': order.date_order,

                        'receipt_ref': receipt_ref,

                        'terminal_name': terminal_name,

                        'order_ref': order_ref,

                        'calculated_tax_amount': 0.0,
                    }

                # -----------------------------------------------------
                # ALL TYPES QTY
                # -----------------------------------------------------

                grouped_data[receipt_ref]['qty'] += qty

                # -----------------------------------------------------
                # ONLY STORABLE QTY
                # -----------------------------------------------------

                grouped_data[receipt_ref]['storable_qty'] += storable_qty

                # -----------------------------------------------------
                # AMOUNTS
                # -----------------------------------------------------

                grouped_data[receipt_ref]['amount_excl'] += subtotal

                grouped_data[receipt_ref]['amount_incl'] += tax_inc_total

                grouped_data[receipt_ref][
                    'calculated_tax_amount'
                ] += calculated_tax_amount

            # ---------------------------------------------------------
            # CREATE NORMAL POS REPORT LINES
            # ---------------------------------------------------------

            vals_list = []

            for receipt_ref, values in grouped_data.items():
                vals_list.append({
                    'nhcl_order_ref': values['order_ref'],

                    'nhcl_bill_receipt_no': values['receipt_ref'],

                    # Existing all-types quantity
                    'nhcl_order_quantity': values['qty'],

                    # Only storable quantity
                    'storable_qty': values['storable_qty'],

                    'nhcl_amount_total': values['amount_excl'],

                    'nhcl_in_amount_total': values['amount_incl'],

                    'nhcl_amount_payment': values['payment'],

                    'nhcl_tax_amount': values['tax_amount'],

                    'nhcl_discount': values['nhcl_discount'],

                    'nhcl_reward_discount': (
                        values['nhcl_reward_discount']
                    ),

                    'nhcl_date_order': values['date'],

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'config_id': values['terminal_name'],

                    'nhcl_pos_hour_report_id': self.id,

                    'nhcl_calculated_tax_amount': (
                        values['calculated_tax_amount']
                    ),

                    'from_date': store.from_date,

                    'to_date': store.to_date,
                })

            if vals_list:
                self.env['nhcl.pos.hour.report.line'].create(
                    vals_list
                )

            # =========================================================
            # EXCHANGE LINES
            # stock.picking -> stock.move
            # nhcl_exchange = True
            # =========================================================

            exchange_move_domain = [
                ('create_date', '>=', from_date),
                ('create_date', '<=', to_date),
                ('state', '=', 'done'),
                ('nhcl_exchange', '=', True),
            ]

            exchange_moves = self.env['stock.move'].search(
                exchange_move_domain
            )

            exchange_vals_list = []

            for exchange_move in exchange_moves:

                picking = exchange_move.picking_id

                if not picking:
                    continue

                # -----------------------------------------------------
                # COMPANY CHECK
                # -----------------------------------------------------

                if (
                        picking.company_id
                        and picking.company_id.id != store.nhcl_company_id.id
                ):
                    continue

                # -----------------------------------------------------
                # POS ORDER / STORE POS ORDER
                #
                # First:
                # stock.picking.nhcl_pos_order.pos_reference
                #
                # If not available:
                # stock.picking.store_pos_order
                #
                # If both are empty:
                # ''
                # -----------------------------------------------------

                pos_order = picking.nhcl_pos_order

                if pos_order and pos_order.pos_reference:
                    bill_receipt_no = pos_order.pos_reference

                elif picking.store_pos_order:
                    bill_receipt_no = picking.store_pos_order

                else:
                    bill_receipt_no = ''

                # -----------------------------------------------------
                # EXCHANGE QUANTITY
                # NEGATIVE
                # -----------------------------------------------------

                exchange_qty = -abs(
                    exchange_move.quantity
                )

                # -----------------------------------------------------
                # EXCHANGE AMOUNTS
                # NEGATIVE
                # -----------------------------------------------------

                exchange_subtotal = -abs(
                    exchange_move.nhcl_price_subtotal
                )

                exchange_total = -abs(
                    exchange_move.nhcl_price_total
                )

                # -----------------------------------------------------
                # CALCULATED TAX
                #
                # price_total - price_subtotal
                # -----------------------------------------------------

                exchange_tax = (
                        exchange_total - exchange_subtotal
                )

                # -----------------------------------------------------
                # CREATE SEPARATE EXCHANGE LINE
                # -----------------------------------------------------

                exchange_vals_list.append({

                    # Stock Picking Name
                    'nhcl_order_ref': picking.name or '',

                    # POS Reference first,
                    # otherwise Store POS Order,
                    # otherwise empty
                    'nhcl_bill_receipt_no': bill_receipt_no,

                    # Negative exchange quantity
                    'nhcl_order_quantity': exchange_qty,

                    # Negative exchange storable quantity
                    'storable_qty': exchange_qty,

                    # Negative exchange subtotal
                    'nhcl_amount_total': exchange_subtotal,

                    # Negative exchange total
                    'nhcl_in_amount_total': exchange_total,

                    # Negative exchange price total
                    'nhcl_amount_payment': exchange_total,

                    'nhcl_discount': picking.amount_discount or 0.0,

                    'nhcl_reward_discount': (
                            picking.amount_reward_discount or 0.0
                    ),

                    'nhcl_reward_discount': 0.0,

                    'nhcl_date_order': exchange_move.create_date,

                    'nhcl_company_id': store.nhcl_company_id.id,

                    'config_id': (
                        picking.return_counter.id
                        if picking.return_counter
                        else False
                    ),

                    'nhcl_pos_hour_report_id': self.id,

                    # price_total - price_subtotal
                    'nhcl_calculated_tax_amount': exchange_tax,

                    'from_date': store.from_date,

                    'to_date': store.to_date,
                })

            # ---------------------------------------------------------
            # CREATE EXCHANGE LINES SEPARATELY
            # ---------------------------------------------------------

            if exchange_vals_list:
                self.env['nhcl.pos.hour.report.line'].create(
                    exchange_vals_list
                )

        # -------------------------------------------------------------
        # OPEN REPORT
        # -------------------------------------------------------------

        return {
            'type': 'ir.actions.act_window',
            'name': 'Bill Wise Sale Report Lines',
            'res_model': 'nhcl.pos.hour.report.line',
            'view_mode': 'tree,pivot',
            'domain': [
                ('nhcl_pos_hour_report_id', '=', self.id)
            ],
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
    # nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_order_quantity = fields.Float(string="Quantity(service prdct)", digits='Product Unit of Measure')
    nhcl_amount_total = fields.Float(string="Amount Total(Excl Tax)")
    nhcl_in_amount_total = fields.Float(string="Amount Total Inc Tax")
    nhcl_amount_paid = fields.Datetime(string="Amount Paid Time")
    nhcl_amount_payment = fields.Float(string="Amount Total(Incl Tax)")
    nhcl_tax_amount = fields.Float(string="Tax Amount From Totals")
    nhcl_discount_amount = fields.Float(string="Discount Amount")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    nhcl_bill_receipt_no = fields.Char(string="Bill Receipt No")
    config_id = fields.Many2one('pos.config', string='Terminal')
    nhcl_discount = fields.Float(string="Manual Discount Amount")
    nhcl_reward_discount = fields.Float(string="Promo Discount Amount")
    nhcl_calculated_tax_amount = fields.Float(string="Tax Amount")
    from_date = fields.Datetime(
        string="From Date"
    )

    to_date = fields.Datetime(
        string="To Date"
    )
    storable_qty = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure"
    )
