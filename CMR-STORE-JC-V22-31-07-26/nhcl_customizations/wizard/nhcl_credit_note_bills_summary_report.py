from odoo import models, fields, api, _

import base64
import io

from datetime import datetime, time
import xlsxwriter
from odoo.tools import format_date


class NHCLCreditNoteBillsReport(models.Model):
    _name = 'nhcl.credit.notes.bills.report'
    _description = "NHCL Credit Note Bills Report"
    _rec_name = 'nhcl_company_id'

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

    from_date = fields.Datetime('From Date', default=_default_from_date)
    to_date = fields.Datetime('To Date', default=_default_to_date)
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    credit_note_bills_report_ids = fields.One2many('nhcl.credit.notes.bills.report.line', 'credit_note_bills_report_id')
    ref_credit_note = fields.Many2one('account.move', string="Credit Note",
                                      domain="[('move_type', '=', 'out_refund')]")
    partner_phone = fields.Char(string="Mobile Phone")
    config_id = fields.Many2one('pos.config', string="Terminal")
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Quantities')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Net Total')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    total_in_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Gross Total')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.credit_note_bills_report_ids
            rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            rec.total_discount_amount = sum(lines.mapped('nhcl_discount_amount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_in_amount_total = sum(lines.mapped('nhcl_in_amount_total'))


    def action_load_data(self):
        # Remove existing lines
        self.credit_note_bills_report_ids.unlink()

        for store in self:
            # 🔹 Fetch POS order lines from local DB
            start_dt = fields.Datetime.to_datetime(store.from_date)
            end_dt = fields.Datetime.to_datetime(store.to_date)
            # start_dt = datetime.combine(store.from_date, time.min)
            # end_dt = datetime.combine(store.to_date, time.max)

            domain = [
                ('stock_picking_type', '=', 'exchange'),
                ('state', '=', 'done'),
                ('date_done', '>=', start_dt),
                ('date_done', '<=', end_dt),
                ('company_id', '=', store.nhcl_company_id.id)
            ]

            if store.ref_credit_note:
                domain.append(('ref_credit_note', '=', store.ref_credit_note.id))

            if store.partner_phone:
                domain.extend([
                    '|',
                    ('customer_phone', '=', store.partner_phone),
                    ('nhcl_phone', '=', store.partner_phone)
                ])

            pickings = self.env['stock.picking'].search(domain)

            vals_list = []
            for picking in pickings:
                if picking.company_type == 'same':
                    order = picking.nhcl_pos_order
                else:
                    pos_domain = [('pos_reference', '=', picking.store_pos_order)]
                    order = self.env['pos.order'].search(pos_domain, limit=1)

                if store.config_id and order and order.config_id.id != store.config_id.id:
                    continue

                total_discount = 0.00
                nhcl_amount_tax = 0.00
                net_amount = 0.00
                gross_amount = 0.00
                for move in picking.move_ids_without_package:
                    nhcl_amount_tax += move.nhcl_price_tax
                    net_amount += (move.nhcl_price_total - move.nhcl_price_tax)
                    gross_amount += move.nhcl_price_total
                nhcl_order_quantity = 0
                for move in picking.move_ids_without_package:
                    if move.quantity > 0:
                        total_discount += ((move.nhcl_rsp * move.quantity) * (move.nhcl_gdiscount + move.nhcl_discount) / 100)
                    if move.quantity and move.product_id.detailed_type == 'product':
                        nhcl_order_quantity += move.quantity
                # Convert date to user timezone
                # date_order = fields.Datetime.context_timestamp(self, picking.date_done)
                date_order = False
                if picking.received_datetime or picking.date_time_nh:
                    date_order = (picking.received_datetime or picking.date_time_nh).strftime("%Y-%m-%d %H:%M:%S")
                vals_list.append({
                    'nhcl_order_ref': picking.name,
                    'ref_credit_note': picking.ref_credit_note.id if picking.ref_credit_note else False,
                    'config_id': order.config_id.id,
                    'partner_phone': order.partner_phone or picking.nhcl_phone or picking.customer_phone,
                    'nhcl_order_quantity': nhcl_order_quantity or picking.total_quantity,
                    'nhcl_amount_total': net_amount,
                    'nhcl_in_amount_total': gross_amount,
                    'nhcl_discount_amount': total_discount,
                    'nhcl_tax_amount': nhcl_amount_tax,
                    # 'nhcl_date_order': date_order.strftime("%Y-%m-%d %H:%M:%S"),
                    'nhcl_date_order': date_order,
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'credit_note_bills_report_id': self.id,
                })

            if vals_list:
                self.env['nhcl.credit.notes.bills.report.line'].create(vals_list)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Bill  Report',
            'res_model': 'nhcl.credit.notes.bills.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('credit_note_bills_report_id', '=', self.id)],
            'context': {
                'default_credit_note_bills_report_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.credit_note_bills_report_ids.unlink()

    def action_get_excel(self):
        # Create a file-like buffer to receive the data
        if not self.credit_note_bills_report_ids:
            self.action_load_data()

        if not self.credit_note_bills_report_ids:
            return False

        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Store', 'Terminal', 'Order Ref', 'Ref. Credit Note', 'Date', 'Phone', 'Quantity', 'Discount', 'Net', 'Tax', 'Gross']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.credit_note_bills_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_company_id.name)
            worksheet.write(row_num, 1, line.config_id.name)
            worksheet.write(row_num, 2, line.nhcl_order_ref)
            worksheet.write(row_num, 2, line.ref_credit_note.name if line.ref_credit_note else '')
            worksheet.write(row_num, 3, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order,
                                                                             date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 4, line.partner_phone)
            worksheet.write(row_num, 5, line.nhcl_order_quantity)
            worksheet.write(row_num, 6, line.nhcl_discount_amount)
            worksheet.write(row_num, 7, line.nhcl_amount_total)
            worksheet.write(row_num, 8, line.nhcl_tax_amount)
            worksheet.write(row_num, 9, line.nhcl_in_amount_total)

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
            'name': f'Credit_Note_bills_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Credit_Note_bills_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_credit_note__lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Bill  Report Lines',
            'res_model': 'nhcl.credit.notes.bills.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('credit_note_bills_report_id', '=', self.id)],
            'context': {
                'default_credit_note_bills_report_id': self.id
            }
        }


class NHCLCreditNoteBillsReportLine(models.Model):
    _name = 'nhcl.credit.notes.bills.report.line'
    _description = "NHCL Credit Note Bills Report line"

    credit_note_bills_report_id = fields.Many2one('nhcl.credit.notes.bills.report')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    config_id = fields.Many2one('pos.config', string="Terminal")
    nhcl_order_ref = fields.Char(string="Reference")
    ref_credit_note = fields.Many2one('account.move', string="Ref. Credit Note")
    nhcl_date_order = fields.Datetime(string="Date")
    partner_phone = fields.Char(string="Phone")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_amount_total = fields.Float(string="Net")
    nhcl_discount_amount = fields.Float(string="Discount Amount")
    nhcl_in_amount_total = fields.Float(string="Gross")
    nhcl_tax_amount = fields.Float(string="Tax Amount")
