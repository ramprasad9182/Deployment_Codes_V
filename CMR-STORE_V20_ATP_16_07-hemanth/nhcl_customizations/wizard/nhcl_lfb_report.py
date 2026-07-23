from odoo import models, fields, api, _
import requests
from datetime import datetime, time
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io
import xlsxwriter
from odoo.fields import Datetime


class PoslfbReportWizard(models.TransientModel):
    _name = 'pos.lfb.report.wizard'
    _description = 'POS lfb Report Wizard'
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
    name = fields.Char('Name',default="POS LFB Report")
    pos_lfb_report_ids = fields.One2many('pos.lfb.report.line','pos_lfb_report_id')

    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    # def get_last_first_bill_num(self):
    #
    #     report_list = []
    #
    #     try:
    #         user_tz = pytz.timezone(self.env.user.tz or 'Asia/Kolkata')
    #
    #         from_date = fields.Datetime.to_datetime(self.from_date)
    #         to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #         for store in self:
    #
    #             # 🔹 Fetch from LOCAL DB (NO API)
    #             orders = self.env['pos.order'].search([
    #                 ('date_order', '>=', from_date),
    #                 ('date_order', '<=', to_date),
    #                 ('state', 'in', ['paid', 'done']),
    #
    #                 # 👉 Adjust based on your system
    #                 ('company_id', '=', store.nhcl_company_id.id)
    #                 # OR:
    #                 # ('config_id', '=', store.pos_config_id.id)
    #             ])
    #
    #             first_bill_no = last_bill_no = 'N/A'
    #
    #             if orders:
    #                 # Sort orders by date_order
    #                 sorted_orders = orders.sorted(key=lambda o: o.date_order)
    #
    #                 first_bill_no = sorted_orders[0].name
    #                 last_bill_no = sorted_orders[-1].name
    #
    #             report_list.append({
    #                 'store_name': store.nhcl_company_id.name,
    #                 'first_bill_no': first_bill_no,
    #                 'last_bill_no': last_bill_no,
    #                 'start_date': fields.Datetime.context_timestamp(
    #                     self, self.from_date
    #                 ).strftime("%d/%m/%y %H:%M:%S"),
    #                 'end_date': fields.Datetime.context_timestamp(
    #                     self, self.to_date
    #                 ).strftime("%d/%m/%y %H:%M:%S"),
    #             })
    #
    #         return self.env.ref(
    #             'nhcl_customizations.report_pos_lfb_pdfsss'
    #         ).report_action(self, data={'doc': report_list})
    #
    #     except Exception as e:
    #         print("Error in First/Last Bill report:", e)
    #         return {'doc': []}

    def get_last_first_bill_num(self):
        try:
            from_date = fields.Datetime.to_datetime(self.from_date)
            to_date = fields.Datetime.to_datetime(self.to_date)

            # Clear existing lines
            self.pos_lfb_report_ids = [(5, 0, 0)]

            line_vals = []

            for store in self:
                domain = [
                    ('order_id.date_order', '>=', from_date),
                    ('order_id.date_order', '<=', to_date),
                    ('company_id', '=', store.nhcl_company_id.id)
                ]

                order_lines = self.env['pos.order.line'].search(domain)

                first_bill_no = 'N/A'
                last_bill_no = 'N/A'

                if order_lines:
                    # Sort manually using order date
                    sorted_lines = order_lines.sorted(
                        key=lambda x: x.order_id.date_order
                    )

                    first_bill_no = sorted_lines[0].order_id.name
                    last_bill_no = sorted_lines[-1].order_id.name

                line_vals.append((0, 0, {
                    'first_bill_no': first_bill_no,
                    'Last_bill_no': last_bill_no,
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'pos_lfb_report_id': self.id
                }))

            self.write({
                'pos_lfb_report_ids': line_vals
            })
            return {
                'type': 'ir.actions.act_window',
                'name': 'POS LFB Report',
                'res_model': 'pos.lfb.report.line',
                'view_mode': 'tree,pivot',
                'domain': [('pos_lfb_report_id', '=', self.id)],
                'context': {
                    'default_pos_lfb_report_id': self.id
                }
            }

        except Exception as e:
            print("Error in First/Last Bill report:", e)
            return {'doc': []}

    def action_lfb_detailed_view(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS LFB Report',
            'res_model': 'pos.lfb.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('pos_lfb_report_id', '=', self.id)],
            'context': {
                'default_pos_lfb_report_id': self.id
            }
        }


    def get_last_first_bill_num_in_excel(self):

        report_list = []

        try:
            from_date = fields.Datetime.to_datetime(self.from_date)
            to_date = fields.Datetime.to_datetime(self.to_date)

            for store in self:
                # 🔹 Domain for orders
                domain = [
                    ('date_order', '>=', from_date),
                    ('date_order', '<=', to_date),
                    ('state', 'in', ['paid', 'done']),

                    # 👉 Adjust based on your system
                    ('company_id', '=', store.nhcl_company_id.id)
                    # OR:
                    # ('config_id', '=', store.pos_config_id.id)
                ]

                # 🔥 FAST METHOD (Best Practice)
                first_order = self.env['pos.order'].search(domain, order="date_order asc", limit=1)
                last_order = self.env['pos.order'].search(domain, order="date_order desc", limit=1)

                # Use tracking_number if exists else name
                first_bill_no = first_order.tracking_number or first_order.name if first_order else 'N/A'
                last_bill_no = last_order.tracking_number or last_order.name if last_order else 'N/A'

                report_list.append({
                    'store_name': store.nhcl_company_id.name,
                    'first_bill_no': first_bill_no,
                    'last_bill_no': last_bill_no,
                    'start_date': fields.Datetime.context_timestamp(
                        self, self.from_date
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    'end_date': fields.Datetime.context_timestamp(
                        self, self.to_date
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                })

            # ================== EXCEL ==================

            buffer = io.BytesIO()
            workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
            worksheet = workbook.add_worksheet('POS Bill Numbers')

            bold = workbook.add_format({'bold': True})

            headers = ['Store', 'First Bill Number', 'Last Bill Number', 'From Date', 'To Date']
            worksheet.write_row(0, 0, headers, bold)

            row = 1
            for line in report_list:
                worksheet.write(row, 0, line['store_name'])
                worksheet.write(row, 1, line['first_bill_no'])
                worksheet.write(row, 2, line['last_bill_no'])
                worksheet.write(row, 3, line['start_date'])
                worksheet.write(row, 4, line['end_date'])
                row += 1

            workbook.close()

            buffer.seek(0)
            excel_data = buffer.getvalue()
            buffer.close()

            encoded_data = base64.b64encode(excel_data)

            attachment = self.env['ir.attachment'].create({
                'name': f'POS_Bill_Numbers_Report_{fields.Date.today()}.xlsx',
                'type': 'binary',
                'datas': encoded_data,
                'store_fname': f'POS_Bill_Numbers_Report_{fields.Date.today()}.xlsx',
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except Exception as e:
            print("Error in bill number report:", e)
            return {'doc': []}

class PoslfbReportline(models.TransientModel):
    _name = 'pos.lfb.report.line'
    _description = 'POS lfb Report Line'

    pos_lfb_report_id = fields.Many2one('pos.lfb.report.wizard', 'LFB Report Line')
    first_bill_no = fields.Char('First Bill Number')
    Last_bill_no = fields.Char('Last Bill Number')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
