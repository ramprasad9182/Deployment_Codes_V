from odoo import models, fields, api, _
import base64
import io
import xlsxwriter

class NHCLCustomerCreditNoteReport(models.TransientModel):
    _name = 'nhcl.customer.credit.note.report'
    _description = "Customer Credit Note Report"

    name = fields.Char(string='Name', default='Customer Credit Note Report')
    company_id = fields.Many2one('res.company', string='Company')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    partner_id = fields.Many2one('res.partner', string='Customer Name')
    phone_no = fields.Char(string='Phone No Search')
    voucher_number = fields.Char(string='Voucher ID Search')
    line_ids = fields.One2many('nhcl.customer.credit.note.report.line', 'report_id', string='Lines')

    def action_load_data(self):
        self.line_ids.unlink()
        for wizard in self:
            domain = []
            if wizard.company_id:
                pos_orders = self.env['pos.order'].search([('company_id', '=', wizard.company_id.id)])
                bill_numbers = pos_orders.mapped('pos_reference')
                domain.extend([
                    '|',
                    ('pos_bill_number', 'in', bill_numbers),
                    ('partner_id.company_id', '=', wizard.company_id.id)
                ])
            if wizard.start_date:
                domain.append(('pos_bill_date', '>=', wizard.start_date))
            if wizard.end_date:
                domain.append(('pos_bill_date', '<=', wizard.end_date))
            if wizard.partner_id:
                domain.append(('partner_id', '=', wizard.partner_id.id))
            if wizard.phone_no:
                domain.append('|')
                domain.append(('partner_id.phone', 'ilike', wizard.phone_no))
                domain.append(('partner_id.mobile', 'ilike', wizard.phone_no))
            if wizard.voucher_number:
                domain.append(('voucher_number', 'ilike', wizard.voucher_number))

            credit_notes = self.env['res.partner.credit.note'].search(domain)
            vals_list = []
            for cn in credit_notes:
                order = self.env['pos.order'].search([('pos_reference', '=', cn.pos_bill_number)], limit=1)
                company = order.company_id if order else cn.partner_id.company_id

                vals_list.append({
                    'report_id': wizard.id,
                    'company_id': company.id if company else False,
                    'partner_id': cn.partner_id.id,
                    'partner_phone': cn.partner_id.phone or cn.partner_id.mobile or '',
                    'voucher_number': cn.voucher_number or '',
                    'pos_bill_number': cn.pos_bill_number or '',
                    'pos_bill_date': cn.pos_bill_date,
                    'total_amount': cn.total_amount,
                    'deducted_amount': cn.deducted_amount,
                    'balance': cn.remaining_amount,
                })
            if vals_list:
                self.env['nhcl.customer.credit.note.report.line'].create(vals_list)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Credit Note Report Lines',
            'res_model': 'nhcl.customer.credit.note.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'company_id': False,
            'start_date': False,
            'end_date': False,
            'partner_id': False,
            'phone_no': False,
            'voucher_number': False,
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

        sheet = workbook.add_worksheet('Customer Credit Notes')
        bold = workbook.add_format({
            'bold': True
        })
        headers = [
            'Company',
            'Customer Name',
            'Phone No',
            # 'Voucher ID',
            # 'POS Bill Number',
            # 'POS Bill Date',
            'Total Amount',
            'Deducted Amount',
            'Balance'
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        row = 1
        for line in self.line_ids:
            sheet.write(row, 0, line.company_id.name or '')
            sheet.write(row, 1, line.partner_id.name or '')
            sheet.write(row, 2, line.partner_phone or '')
            # sheet.write(row, 3, line.voucher_number or '')
            # sheet.write(row, 4, line.pos_bill_number or '')
            # if line.pos_bill_date:
            #     sheet.write(row, 5, line.pos_bill_date.strftime('%d/%m/%Y'))
            # else:
            #     sheet.write(row, 5, '')
            sheet.write(row, 4, line.total_amount)
            sheet.write(row, 5, line.deducted_amount)
            sheet.write(row, 6, line.balance)
            row += 1
        workbook.close()
        buffer.seek(0)
        file_data = buffer.read()
        buffer.close()
        attachment = self.env['ir.attachment'].create({
            'name': 'Customer_Credit_Note_Report.xlsx',
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


class NHCLCustomerCreditNoteReportLine(models.TransientModel):
    _name = 'nhcl.customer.credit.note.report.line'
    _description = "Customer Credit Note Report Line"
    _order = "company_id, partner_id"

    report_id = fields.Many2one('nhcl.customer.credit.note.report', ondelete='cascade')
    company_id = fields.Many2one('res.company', string="Company")
    partner_id = fields.Many2one('res.partner', string="Customer Name")
    partner_phone = fields.Char(string="Phone No")
    voucher_number = fields.Char(string="Voucher ID")
    pos_bill_number = fields.Char(string="POS Bill Number")
    pos_bill_date = fields.Date(string="POS Bill Date")
    total_amount = fields.Float(string="Credit Issued Amount")
    deducted_amount = fields.Float(string="Utilized Amount")
    balance = fields.Float(string="Remaining Balance")
