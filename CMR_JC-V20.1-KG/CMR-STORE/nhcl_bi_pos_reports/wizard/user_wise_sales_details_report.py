# -*- coding: utf-8 -*-
import base64
from io import BytesIO
from odoo import models, fields
from odoo.tools.misc import xlwt
from odoo.exceptions import ValidationError


class UserWiseSaleDetailReport(models.TransientModel):
    _name = 'user.wise.sales.detail.report'
    _description = 'User Wise Sales Detail Report'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    user_id = fields.Many2one('res.users', string='User id', default=lambda self: self.env.user)
    select_state = fields.Selection([
        ('all', 'All'),
        ('draft', 'New'),
        ('paid', 'Paid'),
        ('done', 'Posted'),
        ('invoiced', 'Invoiced'),
    ], string='Status', default='all')
    pos_orders = fields.Many2many('pos.order')
    company_ids = fields.Many2many('res.company', string='Companies')
    user_ids = fields.Many2many('res.users', string='User')
    file_name = fields.Char('Excel File', readonly=True)
    data = fields.Binary(string="File")

    def pos_order_record_data(self):
        companies = self.company_ids.ids
        if len(companies) > 0:
            selected_companies = companies
        else:
            selected_companies = self.env.user.company_ids.ids
        data_all = {}
        list1 = []
        if self.select_state == 'all':
            list1.extend(['draft', 'paid', 'done', 'invoiced'])
        elif self.select_state == 'draft':
            list1.extend(['draft'])
        elif self.select_state == 'paid':
            list1.extend(['paid'])
        elif self.select_state == 'done':
            list1.extend(['done'])
        elif self.select_state == 'invoiced':
            list1.extend(['invoiced'])
        elif self.select_state == False:
            list1.extend(['draft', 'paid', 'done', 'invoiced'])
        status = ('state', 'in', list1)
        if len(self.user_ids.ids) == 0:
            self.user_ids = self.user_id

        for user in self.user_ids:
            pos_orders = self.env['pos.order'].search([('date_order', '>=', self.start_date),
                                                       ('date_order', '<=', self.end_date),
                                                       ('company_id', 'in', selected_companies),
                                                       ('user_id', '=', user.id), status])
            list2 = []
            total = [0.0]
            for order in pos_orders:
                list2.append(
                    [order.name, str(order.date_order.strftime("%d/%m/%Y")), order.partner_id.name, order.amount_paid])
            for total_count in list2:
                total[0] += total_count[3]
            data_all.update({user.name: {'lines': list2, 'total': total}
                             })
        return data_all

    def company_record(self):
        comp_name = []
        for comp in self.company_ids:
            comp_name.append(comp.name)
        listtostr = ', '.join([str(elem) for elem in comp_name])
        return listtostr

    def status_record(self):
        if self.select_state == False:
            return self.select_state
        else:
            return self.select_state.title()

    def user_wise_sale_detail_pdf_report(self):
        if self.end_date < self.start_date:
            raise ValidationError('Enter End Date greater then Start Date')
        datas = {
            'ids': self._ids,
            'model': 'user.wise.sales.detail.report',
            'form': self.read()[0],
            'sale_details': self.pos_order_record_data(),
        }
        return self.env.ref('nhcl_bi_pos_reports.user_wise_sales_detail_report_action').report_action(self.id,
                                                                                                      data=datas)

    def user_wise_sale_detail_xls_report(self):
        if self.end_date < self.start_date:
            raise ValidationError('Enter End Date greater then Start Date')
        workbook = xlwt.Workbook()
        stylePC = xlwt.XFStyle()
        worksheet = workbook.add_sheet('User Wise POS Sales Detail Report')
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
        style_header = xlwt.easyxf(
            "font:height 300; font: name Liberation Sans, bold on,color black; align: vert centre, horiz center;pattern: pattern solid, pattern_fore_colour gray25;")
        style_line_heading = xlwt.easyxf(
            "font: name Liberation Sans, bold on;align: horiz centre; pattern: pattern solid, pattern_fore_colour gray25;")
        style_line_heading_left = xlwt.easyxf(
            "font: name Liberation Sans, bold on;align: horiz left; pattern: pattern solid, pattern_fore_colour gray25;")

        worksheet.write_merge(0, 1, 0, 4, 'User Wise POS Sales Detail Report', style=stylePC)
        worksheet.col(2).width = 5600
        worksheet.write_merge(2, 2, 0, 4, 'Companies: ' + str(self.company_record()), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz center;"))

        worksheet.write(3, 0, 'Start Date: ' + str(self.start_date.strftime('%d-%m-%Y')), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on;"))
        worksheet.write(3, 2, 'End Date: ' + str(
            self.end_date.strftime('%d-%m-%Y')), style=xlwt.easyxf(
            "font: name Liberation Sans, bold on; align: horiz left;"))
        if self.select_state == False:
            worksheet.write(3, 4, 'Status: ', style=xlwt.easyxf(
                "font: name Liberation Sans, bold on;align: horiz left;"))
        else:
            worksheet.write(3, 4, 'Status: ' + self.status_record(), style=xlwt.easyxf(
                "font: name Liberation Sans, bold on;align: horiz left;"))
        pos_orders = self.pos_order_record_data()
        row = 5
        for person in pos_orders:
            row += 1
            worksheet.write_merge(row, row, 0, 3, 'POS Sale Person:' + person,
                                  style=style_line_heading)
            list1 = ['Order Number', 'Order Date', 'Customer', 'Total']
            row += 2
            worksheet.col(0).width = 5000
            worksheet.write(row, 0, list1[0], style=style_line_heading_left)
            worksheet.col(1).width = 5000
            worksheet.write(row, 1, list1[1], style1)
            worksheet.col(2).width = 5000
            worksheet.write(row, 2, list1[2], style1)
            worksheet.col(3).width = 5000
            worksheet.write(row, 3, list1[3], style1)
            row = row + 1
            for order in pos_orders[person]['lines']:
                worksheet.write(row, 0, order[0])
                worksheet.write(row, 1, order[1])
                worksheet.write(row, 2, order[2])
                worksheet.write(row, 3, order[3])
                row += 1
            row += 1
            worksheet.write(row, 2, 'Total', style=xlwt.easyxf(
                "font: name Liberation Sans, bold on; align: horiz center;"))
            worksheet.write(row, 3, pos_orders[person]['total'][0], style=xlwt.easyxf(
                "font: name Liberation Sans; align: horiz right;"))
            row = row + 1
        file_data = BytesIO()
        workbook.save(file_data)
        self.write({
            'data': base64.encodebytes(file_data.getvalue()),
            'file_name': 'User Wise POS Sales Detail Report.xls'
        })
        action = {
            'type': 'ir.actions.act_url',
            'name': 'User Wise POS Sales Detail Report',
            'url': '/web/content/user.wise.sales.detail.report/%s/data/User Wise Sales Detail Report.xls?download=true' % (
                self.id),
            'target': 'self',
        }
        return action
