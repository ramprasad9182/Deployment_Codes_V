from odoo import models, fields, api, _
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclHSNTaxReport(models.Model):
    _name = 'nhcl.hsn.tax.report'
    _description = "hsn tax report main"
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
    nhcl_pos_hsn_tax_ids = fields.One2many('nhcl.hsn.tax.report.line', 'nhcl_pos_hsn_tax_id')
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qtys')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Gross Total')
    total_taxable_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Net Total')
    total_cgst_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total CGST')
    total_sgst_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total SGST')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    name = fields.Char(string='Name', default='HSN Wise Tax Report')
    l10n_in_hsn_code = fields.Char(string="HSN/SAC Code", help="Harmonized System Nomenclature/Services Accounting Code")
    tax_id = fields.Many2one('account.tax', string='Tax')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_pos_hsn_tax_ids
            rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            rec.total_taxable_amount = sum(lines.mapped('nhcl_taxable_amount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_cgst_amount = sum(lines.mapped('nhcl_cgst_amount'))
            rec.total_sgst_amount = sum(lines.mapped('nhcl_sgst_amount'))

    def get_hsn_with_tax_wise_report(self):
        self.nhcl_pos_hsn_tax_ids.unlink()

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self:

            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id', '=', store.nhcl_company_id.id),
            ]

            # Filter by HSN code
            if self.l10n_in_hsn_code:
                domain.append((
                    'product_id.l10n_in_hsn_code',
                    '=',
                    self.l10n_in_hsn_code
                ))

            # Filter by Tax
            if self.tax_id:
                domain.append((
                    'tax_ids',
                    'in',
                    self.tax_id.id
                ))

            pos_lines = self.env['pos.order.line'].search(domain)

            grouped_data = {}

            for line in pos_lines:
                product = line.product_id
                if not product:
                    continue

                hsn_code = product.l10n_in_hsn_code or 'N/A'

                tax = line.tax_ids[:1]
                tax_name = tax.name if tax else 'No Tax'

                qty = line.qty
                subtotal = line.price_subtotal
                subtotal_incl = line.price_subtotal_incl
                tax_amount = subtotal_incl - subtotal

                key = (store.id, hsn_code, tax_name)

                if key not in grouped_data:
                    grouped_data[key] = {
                        'qty': 0,
                        'taxable': 0.0,
                        'total': 0.0,
                        'tax': 0.0,
                        'cgst': 0.0,
                        'sgst': 0.0,
                    }

                grouped_data[key]['qty'] += qty
                grouped_data[key]['taxable'] += subtotal
                grouped_data[key]['total'] += subtotal_incl
                grouped_data[key]['tax'] += tax_amount
                grouped_data[key]['cgst'] += tax_amount / 2
                grouped_data[key]['sgst'] += tax_amount / 2

            vals_list = []
            for (store_id, hsn, tax_name), vals in grouped_data.items():
                vals_list.append({
                    'nhcl_hsn': hsn,
                    'nhcl_tax': tax_name,
                    'nhcl_order_quantity': vals['qty'],
                    'nhcl_amount_total': vals['total'],
                    'nhcl_taxable_amount': vals['taxable'],
                    'nhcl_tax_amount': vals['tax'],
                    'nhcl_cgst_amount': vals['cgst'],
                    'nhcl_sgst_amount': vals['sgst'],
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'nhcl_pos_hsn_tax_id': self.id
                })

            if vals_list:
                self.env['nhcl.hsn.tax.report.line'].create(vals_list)

        return {
            'type': 'ir.actions.act_window',
            'name': 'HSN TAX Report Lines',
            'res_model': 'nhcl.hsn.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hsn_tax_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hsn_tax_id': self.id
            }
        }

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_pos_hsn_tax_ids.unlink()


    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['HSN', 'TAX%', 'BILLQTY', 'NETAMT', 'TAXABLEAMT', 'CGSTAMT', 'SGSTAMT']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_hsn_tax_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_hsn)
            worksheet.write(row_num, 1, line.nhcl_tax)
            worksheet.write(row_num, 2, line.nhcl_order_quantity)
            worksheet.write(row_num, 3, line.nhcl_amount_total)
            worksheet.write(row_num, 4, line.nhcl_taxable_amount)
            worksheet.write(row_num, 5, line.nhcl_cgst_amount)
            worksheet.write(row_num, 6, line.nhcl_sgst_amount)

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
            'name': f'POS_HSN_Wise_Tax_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_HSN_Wise_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_hsn_tax_lines(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'HSN TAX Report Lines',
            'res_model': 'nhcl.hsn.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hsn_tax_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hsn_tax_id': self.id
            }
        }


class NhclHSNTaxReportLine(models.Model):
    _name = 'nhcl.hsn.tax.report.line'
    _description = "hsn tax report"

    nhcl_pos_hsn_tax_id = fields.Many2one('nhcl.hsn.tax.report', string="HSN Tax Report")
    nhcl_hsn = fields.Char(string="HSN")
    nhcl_tax = fields.Char(string="Tax%")
    nhcl_order_quantity = fields.Integer(string="BillQty")
    nhcl_amount_total = fields.Float(string="Gross AMT")
    nhcl_taxable_amount = fields.Float(string="NET AMT")
    nhcl_tax_amount = fields.Float(string="TAX AMT")
    nhcl_cgst_amount = fields.Float(string="CGST AMT")
    nhcl_sgst_amount = fields.Float(string="SGST AMT")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
