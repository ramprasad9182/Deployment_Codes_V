# -*- coding: utf-8 -*-
import base64
from io import BytesIO
from odoo import models, fields
from odoo.tools.misc import xlwt
from xlwt import easyxf
from odoo.exceptions import ValidationError


class POSTaxSummaryReport(models.TransientModel):
    _name = 'pos.tax.summary.report'
    _description = 'POS Tax Summary Report'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    pos_conig_ids = fields.Many2many(
        'pos.config',
        string='Pos Configuration',
    )
    user_ids = fields.Many2many('res.users', string='User')
    company_ids = fields.Many2many('res.company', string='Companies')
    file_name = fields.Char('Excel File', readonly=True)
    data = fields.Binary(string="File")

    def company_record(self):
        comp_name = []
        for comp in self.company_ids:
            comp_name.append(comp.name)
        listtostr = ', '.join([str(elem) for elem in comp_name])
        return listtostr

    def tax_summary_data(self):
        users = self.user_ids.ids
        if len(users) > 0:
            selected_users = users
        else:
            selected_users = self.env.user.id

        companies = self.company_ids.ids
        if len(companies) > 0:
            selected_companies = companies
        else:
            selected_companies = self.env.user.company_ids.ids

        data_all = {}
        list2 = []
        total = [0.0]
        all_tax = {}
        pos_orders = self.env['pos.order'].search([('date_order', '>=', self.start_date),
                                                   ('date_order', '<=', self.end_date),
                                                   ('company_id', 'in', selected_companies),
                                                   ('user_id', 'in', selected_users),
                                                   ('session_id.config_id', 'in', self.pos_conig_ids.ids)])
        for order in pos_orders:
            for line in order.lines:
                if line.tax_ids:
                    for tax in line.tax_ids:
                        var_a = 0.0
                        var_b = 0.0
                        tax_amount = 0.0
                        product_price = 0.0
                        product_price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                        var_a = (tax.amount * product_price)
                        var_b = var_a / 100
                        tax_amount = var_b * line.qty
                        list2.append([tax.name, order.name, line.price_subtotal_incl, tax_amount])
                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_ids.compute_all(line.price_subtotal, line.order_id.currency_id,
                                                     product=line.product_id)
                    for tax in taxes.get('taxes', []):
                        if tax.get('name') not in all_tax:
                            all_tax.update({tax.get('name'): tax.get('amount', 0)})
                        else:
                            all_tax[tax.get('name')] += tax.get('amount', 0)

        for total_count in list2:
            total[0] += total_count[3]
        data_all.update({'lines': list2, 'total': total, 'all_tax': all_tax})
        return data_all

    def pos_tax_summary_receipt(self):
        if self.end_date < self.start_date:
            raise ValidationError('Enter End Date greater then Start Date')
        datas = {
            'ids': self._ids,
            'model': 'pos.tax.summary.report',
            'form': self.read()[0],
            'tax_details': self.tax_summary_data(),
        }
        return self.env.ref('nhcl_bi_pos_reports.action_pos_tax_summary_report').report_action(self.id, data=datas)

    def pos_tax_xls_report(self):
        if self.end_date < self.start_date:
            raise ValidationError('Enter End Date greater then Start Date')
        workbook = xlwt.Workbook()
        stylePC = xlwt.XFStyle()
        worksheet = workbook.add_sheet('User Wise Sales Detail Report')
        bold = xlwt.easyxf("font: bold on; pattern: pattern solid, fore_colour gray25;")
        alignment = xlwt.Alignment()
        alignment.horz = xlwt.Alignment.HORZ_CENTER
        stylePC.alignment = alignment
        alignment = xlwt.Alignment()
        alignment.horz = xlwt.Alignment.HORZ_CENTER
        alignment_num = xlwt.Alignment()
        alignment_num.horz = xlwt.Alignment.HORZ_RIGHT
        horz_style = xlwt.XFStyle()
        horz_style.alignment = alignment_num
        align_num = xlwt.Alignment()
        align_num.horz = xlwt.Alignment.HORZ_RIGHT
        horz_style_pc = xlwt.XFStyle()
        horz_style_pc.alignment = alignment_num
        style1 = horz_style
        font = xlwt.Font()
        font1 = xlwt.Font()
        borders = xlwt.Borders()
        borders.bottom = xlwt.Borders.THIN
        font.bold = True
        font1.bold = True
        font.height = 400
        stylePC.font = font
        style1.font = font1
        stylePC.alignment = alignment
        pattern = xlwt.Pattern()
        pattern1 = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern1.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['gray25']
        pattern1.pattern_fore_colour = xlwt.Style.colour_map['gray25']
        stylePC.pattern = pattern
        style1.pattern = pattern
        medium_heading_style = easyxf(
            'font:name Arial, bold on,height 250, color  black; align: vert centre, horz center ;')
        style_header = xlwt.easyxf(
            "font:height 300; font: name Liberation Sans, bold on,color black; align: vert centre, horiz center;pattern: pattern solid, pattern_fore_colour gray25;")
        style_line_heading = xlwt.easyxf(
            "font: name Liberation Sans, bold on;align: horiz centre; pattern: pattern solid, pattern_fore_colour gray25;")
        style_line_heading_left = xlwt.easyxf(
            "font: name Liberation Sans, bold on;align: horiz left; pattern: pattern solid, pattern_fore_colour gray25;")
        test_style = xlwt.easyxf(
            "font: name Liberation Sans, bold off;align: horiz left;")
        worksheet.write_merge(0, 1, 0, 3, 'POS Tax Summary Report', style=stylePC)
        worksheet.col(2).width = 5600
        worksheet.write_merge(2, 2, 0, 3, 'Companies: ' + str(self.company_record()), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz center;"))

        worksheet.write(3, 0, 'Start Date: ' + str(self.start_date.strftime('%d-%m-%Y')), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on;"))
        worksheet.write(3, 3, 'End Date: ' + str(
            self.end_date.strftime('%d-%m-%Y')), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz left;"))
        pos_tax_records = self.tax_summary_data()
        row = 5
        row += 1
        list1 = ['Tax Name', 'Order Ref', 'Base Amount', 'Tax Amount']
        row += 2
        worksheet.col(0).width = 5000
        worksheet.write(row, 0, list1[0], style=style_line_heading_left)
        worksheet.col(1).width = 5000
        worksheet.write(row, 1, list1[1], style=style_line_heading_left)
        worksheet.col(2).width = 5000
        worksheet.write(row, 2, list1[2], style=style_line_heading_left)
        worksheet.col(3).width = 5000
        worksheet.write(row, 3, list1[3], style=style_line_heading_left)
        worksheet.col(4).width = 5000
        row = row + 1
        if pos_tax_records:
            for order1 in pos_tax_records['lines']:
                worksheet.write(row, 0, order1[0])
                worksheet.write(row, 1, order1[1])
                worksheet.write(row, 2, order1[2], style=test_style)
                worksheet.write(row, 3, order1[3], style=test_style)
                row += 1
        row += 1
        worksheet.write(row, 2, 'Total', style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz center;"))
        if pos_tax_records:
            worksheet.write(row, 3, pos_tax_records['total'][0], style=style_line_heading_left)

        row += 2
        worksheet.write_merge(row, row, 0, 1, 'Tax Summary', medium_heading_style)
        list2 = ['Tax Name', 'Tax Amount']
        row += 2
        worksheet.col(0).width = 5000
        worksheet.write(row, 0, list1[0], style=style_line_heading_left)
        worksheet.col(1).width = 5000
        worksheet.write(row, 1, list1[1], style=style_line_heading_left)

        row = row + 1
        if pos_tax_records:
            for order2 in pos_tax_records['all_tax']:
                worksheet.write(row, 0, order2)
                worksheet.write(row, 1, pos_tax_records['all_tax'][order2], style=test_style)
                row += 1
        row += 1
        worksheet.write(row, 0, 'Total', style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz center;"))
        if pos_tax_records:
            worksheet.write(row, 1, pos_tax_records['total'][0], style=style_line_heading_left)

        file_data = BytesIO()
        workbook.save(file_data)
        self.write({
            'data': base64.encodebytes(file_data.getvalue()),
            'file_name': 'POS Tax Summary Report.xls'
        })
        action = {
            'type': 'ir.actions.act_url',
            'name': 'POS Tax Summary Report',
            'url': '/web/content/pos.tax.summary.report/%s/data/POS Tax Summary Report.xls?download=true' % (self.id),
            'target': 'self',
        }
        return action
