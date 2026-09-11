# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import base64
import io
from datetime import datetime, time
import xlsxwriter
from odoo.tools import format_date


class NHCLPosMopChangeReport(models.Model):
    _name = 'nhcl.pos.mop.change.report'
    _description = "POS MOP Change Report"
    _rec_name = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(0, 0, 0))
        )

    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(23, 59, 59))
        )

    name = fields.Char(string='Name', default='POS MOP Change Report')
    start_date = fields.Datetime(string='Start Date', default=_default_from_date)
    end_date = fields.Datetime(string='End Date', default=_default_to_date)
    company_id = fields.Many2one('res.company', string='Store Name')
    config_id = fields.Many2one('pos.config', string='Terminal')
    session_id = fields.Many2one('pos.session', string='Session')
    line_ids = fields.One2many('nhcl.pos.mop.change.report.line', 'report_id', string='Lines')
    total_amount = fields.Float(compute="_compute_total_amount", string='Total Amount')

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.line_ids.mapped('amount'))

    def action_load_data(self):
        self.line_ids.unlink()

        for wizard in self:
            domain = [('old_payment_method_id', '!=', False)]

            if wizard.company_id:
                domain.append(('pos_order_id.company_id', '=', wizard.company_id.id))
            if wizard.config_id:
                domain.append(('pos_order_id.config_id', '=', wizard.config_id.id))
            if wizard.session_id:
                domain.append(('pos_order_id.session_id', '=', wizard.session_id.id))
            if wizard.start_date:
                domain.append(('pos_order_id.date_order', '>=', wizard.start_date))
            if wizard.end_date:
                domain.append(('pos_order_id.date_order', '<=', wizard.end_date))

            payments = self.env['pos.payment'].search(domain, order='order_date desc, id desc')
            # Filter out records where old_payment_method_id equals payment_method_id
            payments = payments.filtered(lambda p: p.old_payment_method_id and p.old_payment_method_id != p.payment_method_id)

            vals_list = []
            seq = 1
            for payment in payments:
                order = payment.pos_order_id
                cashier_name = order.employee_id.name or (order.user_id.name if order.user_id else '') or getattr(payment, 'nhcl_cashier', '') or ''
                vals_list.append({
                    'report_id': wizard.id,
                    'sequence_no': seq,
                    'bill_ref': order.pos_reference or order.name or '',
                    'order_ref': order.name or '',
                    'date': order.date_order or payment.payment_date,
                    'session_id': order.session_id.id if order.session_id else False,
                    'cashier': cashier_name,
                    'amount': payment.amount,
                    'payment_method_id': payment.payment_method_id.id,
                    'old_payment_method_id': payment.old_payment_method_id.id,
                    'company_id': order.company_id.id if order.company_id else False,
                    'config_id': order.config_id.id if order.config_id else False,
                    'pos_order_id': order.id,
                })
                seq += 1

            if vals_list:
                self.env['nhcl.pos.mop.change.report.line'].create(vals_list)

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS MOP Change Report Lines',
            'res_model': 'nhcl.pos.mop.change.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'company_id': False,
            'config_id': False,
            'session_id': False,
            'start_date': False,
            'end_date': False,
        })
        self.line_ids.unlink()

    def action_get_excel(self):
        if not self.line_ids:
            self.action_load_data()
        if not self.line_ids:
            return False

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet('MOP Change Report')

        bold = workbook.add_format({'bold': True})
        headers = ['S.NO', 'Bill Ref', 'Order Ref', 'Date', 'Session', 'Cashier', 'Amount', 'Payment Method', 'Old Payment']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        for row_num, line in enumerate(self.line_ids, start=1):
            if line.date:
                local_date = fields.Datetime.context_timestamp(self, line.date)
                date_str = local_date.strftime('%d/%m/%Y %H:%M:%S')
            else:
                date_str = ''
            worksheet.write(row_num, 0, line.sequence_no)
            worksheet.write(row_num, 1, line.bill_ref or '')
            worksheet.write(row_num, 2, line.order_ref or '')
            worksheet.write(row_num, 3, date_str)
            worksheet.write(row_num, 4, line.session_id.name if line.session_id else '')
            worksheet.write(row_num, 5, line.cashier or '')
            worksheet.write(row_num, 6, line.amount)
            worksheet.write(row_num, 7, line.payment_method_id.name if line.payment_method_id else '')
            worksheet.write(row_num, 8, line.old_payment_method_id.name if line.old_payment_method_id else '')

        workbook.close()
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        encoded_data = base64.b64encode(excel_data)
        attachment = self.env['ir.attachment'].create({
            'name': f'POS_MOP_Change_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_MOP_Change_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class NHCLPosMopChangeReportLine(models.Model):
    _name = 'nhcl.pos.mop.change.report.line'
    _description = "POS MOP Change Report Line"
    _order = "sequence_no asc, date desc"

    report_id = fields.Many2one('nhcl.pos.mop.change.report', string="Report", ondelete='cascade')
    sequence_no = fields.Integer(string="S.NO")
    bill_ref = fields.Char(string="Bill Ref")
    order_ref = fields.Char(string="Order Ref")
    date = fields.Datetime(string="Date")
    session_id = fields.Many2one('pos.session', string="Session")
    cashier = fields.Char(string="Cashier")
    amount = fields.Float(string="Amount")
    payment_method_id = fields.Many2one('pos.payment.method', string="Payment Method")
    old_payment_method_id = fields.Many2one('pos.payment.method', string="Old Payment")
    company_id = fields.Many2one('res.company', string="Store Name")
    config_id = fields.Many2one('pos.config', string="Terminal")
    pos_order_id = fields.Many2one('pos.order', string="POS Order")
