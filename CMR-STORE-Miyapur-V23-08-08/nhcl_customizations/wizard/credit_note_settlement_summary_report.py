from odoo import models, fields, api, _
import base64
import io
import datetime
import xlsxwriter
from datetime import datetime, time
from odoo.tools import format_date



class NHCLCreditNoteSettlementReport(models.Model):
    _name = 'credit.note.settlement.report'
    _description = "Credit Note Settlement Summary Report"
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

    # from_date = fields.Date(string="From Date",default=_default_from_date)
    # to_date = fields.Date(string="To Date",default=_default_from_date)
    from_date = fields.Datetime(string="From Date", default=_default_from_date)
    to_date = fields.Datetime(string="To Date", default=_default_to_date)
    nhcl_company_id = fields.Many2one('res.company',  string="Store Name" )
    line_ids = fields.One2many('credit.note.settlement.line', 'report_id',string="Lines" )
    partner_phone = fields.Char(string="Mobile Phone")
    name = fields.Char(string='Name', default='Credit Note Settlement Summary Report')
    search_bill_no = fields.Many2one( 'pos.order',string="Bill No")
    search_terminal_id = fields.Many2one('pos.config',string="Terminal")
    total_net_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Net Total')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    total_gross_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Gross Total')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    credit_note_nos = fields.Many2many('res.partner.credit.note',string="Credit Note Nos")
    name = fields.Char(string='Name', default='Credit Note Settlement Summary Report')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_net_amount = sum(lines.mapped('net_amount'))
            rec.total_discount_amount = sum(lines.mapped('discount_amount'))
            rec.total_gross_amount = sum(lines.mapped('gross_amount'))
            rec.total_tax_amount = sum(lines.mapped('tax_amount'))

    def action_load_data(self):
        self.line_ids.unlink()

        for rec in self:
            if not rec.from_date or not rec.to_date:
                return

            start_dt = rec.from_date
            end_dt = rec.to_date

            payment_method = self.env['pos.payment.method'].search([
                ('name', 'ilike', 'Credit Note Settlement')
            ], limit=1)

            if not payment_method:
                return

            # ✅ Build ONE clean domain
            domain = [
                ('payment_method_id', '=', payment_method.id),
                ('payment_date', '>=', start_dt),
                ('payment_date', '<=', end_dt),
            ]

            if rec.nhcl_company_id:
                domain.append(('pos_order_id.company_id', '=', rec.nhcl_company_id.id))

            if rec.search_terminal_id:
                domain.append(('pos_order_id.config_id', '=', rec.search_terminal_id.id))

            if rec.search_bill_no:
                domain.append(('pos_order_id', '=', rec.search_bill_no.id))

            # ✅ SAFE phone filter (no invalid fields)
            if rec.partner_phone:
                domain.append(('pos_order_id.partner_phone', '=', rec.partner_phone))

            # ✅ SINGLE search
            payments = self.env['pos.payment'].search(domain)

            vals_list = []
            processed_orders = set()  # faster than list

            for pay in payments:
                order = pay.pos_order_id
                if not order:
                    continue

                if order.id in processed_orders:
                    continue

                processed_orders.add(order.id)

                gross = pay.amount

                # check if any non-credit-note payment exists
                other_payments = order.payment_ids.filtered(
                    lambda x:
                    x.payment_method_id.id != payment_method.id
                    and x.amount > 0
                )

                if other_payments:
                    tax = 0.0
                    net = 0.0
                else:
                    order_total = order.amount_total or 1
                    ratio = gross / order_total
                    tax = order.amount_tax * ratio
                    net = gross - tax

                vals_list.append({
                    'report_id': rec.id,
                    'nhcl_company_id': order.company_id.id,
                    'config_id': order.config_id.id,
                    'date_order': order.date_order,
                    'partner_phone': order.partner_phone or '',
                    'bill_no': order.pos_reference or '',
                    'credit_note_nos': [(6, 0, order.credit_ids.mapped('partner_credit_id').ids)],
                    'net_amount': net,
                    'gross_amount': gross,
                    'tax_amount': tax,
                    'payment_methods': pay.payment_method_id.name,
                })

            if vals_list:
                self.env['credit.note.settlement.line'].create(vals_list)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Setttlement Summary Report',
            'res_model': 'credit.note.settlement.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }

    def action_reset(self):
        self.write({
            'from_date': False,
            'to_date': False,
            'nhcl_company_id': False,
            'partner_phone': False,
            'search_bill_no': False,
            'search_terminal_id': False,
        })
        self.line_ids.unlink()

    def action_get_excel(self):
        if not self.line_ids:
            self.action_load_data()
        if not self.line_ids:
            return False
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            buffer,
            {'in_memory': True}
        )

        sheet = workbook.add_worksheet('Report')
        bold = workbook.add_format({
            'bold': True
        })
        headers = [
            'Store',
            'Terminal',
            'Date',
            'Customer Phone',
            'Base Bill No',
            'Credit Note No',
            'Net',
            'Discount',
            'Gross',
            'Tax',
            'Payment Method'
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        row = 1
        for line in self.line_ids:
            sheet.write(row, 0, line.nhcl_company_id.name)
            sheet.write(row, 1, line.config_id.name)
            local_dt = fields.Datetime.context_timestamp(self, line.date_order)
            sheet.write(row, 2, local_dt.strftime('%d/%m/%Y %H:%M:%S'))
            sheet.write(row, 3, line.partner_phone)
            sheet.write(row, 4, line.bill_no)
            sheet.write(row, 5, line.credit_note_nos)
            sheet.write(row, 6, line.net_amount)
            sheet.write(row, 7, line.discount_amount)
            sheet.write(row, 8, line.gross_amount)
            sheet.write(row, 9, line.tax_amount)
            sheet.write(row, 10, line.payment_methods)
            row += 1
        workbook.close()
        buffer.seek(0)
        file_data = buffer.read()
        buffer.close()
        attachment = self.env['ir.attachment'].create({
            'name': 'Credit_Note_Settlement_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'mimetype':
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }

    def action_view_credit_note_settlement_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Setttlement Summary Report Lines',
            'res_model': 'credit.note.settlement.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }

class NHCLCreditNoteSettlementLine(models.Model):
    _name = 'credit.note.settlement.line'
    _description = "Credit Note Settlement Summary Line"

    report_id = fields.Many2one('credit.note.settlement.report')
    nhcl_company_id = fields.Many2one( 'res.company', string="Store Name" )
    config_id = fields.Many2one('pos.config', string="Terminal" )
    date_order = fields.Datetime(string="Date")
    partner_phone = fields.Char(string="Customer Phone No")
    bill_no = fields.Char(string="Bill No")
    net_amount = fields.Float(string="Net")
    discount_amount = fields.Float(string="Discount")
    gross_amount = fields.Float(string="Gross")
    tax_amount = fields.Float(string="Tax Amount")
    payment_methods = fields.Char(string="Payment Method")
    credit_note_nos = fields.Many2many('res.partner.credit.note',string="Credit Note Nos")
