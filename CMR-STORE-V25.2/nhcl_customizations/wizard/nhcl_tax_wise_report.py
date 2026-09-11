from odoo import models,fields,api,_
import requests
from datetime import datetime, time, timedelta
import pytz
import re


import xmlrpc.client


from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from odoo.http import  request

from collections import defaultdict



class PosTaxReportWizard(models.TransientModel):
    _name = 'pos.tax.report.wizard'
    _description = 'POS tax Report Wizard'

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
    name = fields.Char('Name',default="POS Tax Wise Report")
    pos_tax_report_ids = fields.One2many('pos.tax.report.line','pos_tax_report_id')

    tax_amount = fields.Float(string='Tax Amount', compute='_compute_nhcl_show_totals')
    cgst_amount = fields.Float(string='CGST Amount', compute='_compute_nhcl_show_totals')
    sgst_amount = fields.Float(string='SGST Amount', compute='_compute_nhcl_show_totals')
    igst_amount = fields.Float(string='IGST Amount', compute='_compute_nhcl_show_totals')
    total_tax_amount = fields.Float(string='Total Tax Amount', compute='_compute_nhcl_show_totals')

    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.pos_tax_report_ids
            rec.tax_amount = sum(lines.mapped('tax_amount'))
            rec.cgst_amount = sum(lines.mapped('cgst_amount'))
            rec.sgst_amount = sum(lines.mapped('sgst_amount'))
            rec.igst_amount = sum(lines.mapped('igst_amount'))
            rec.total_tax_amount = sum(lines.mapped('total_tax_amount'))




    def get_tax_summery_report(self):
        try:
            from_date = fields.Datetime.to_datetime(self.from_date)
            to_date = fields.Datetime.to_datetime(self.to_date)

            # Clear old lines
            self.pos_tax_report_ids.unlink()

            normal_tax_data = defaultdict(lambda: {
                'taxable_amt': 0.0,
                'total_amt': 0.0,
                'tax_amt': 0.0,
                'cgst_amt': 0.0,
                'sgst_amt': 0.0,
                'igst_amt': 0.0
            })

            exchange_tax_data = defaultdict(lambda: {
                'taxable_amt': 0.0,
                'total_amt': 0.0,
                'tax_amt': 0.0,
                'cgst_amt': 0.0,
                'sgst_amt': 0.0,
                'igst_amt': 0.0
            })

            for store in self:
                # ---------------------------------------------------------
                # 1. FETCH NORMAL POS LINES
                # ---------------------------------------------------------
                domain = [
                    ('order_id.date_order', '>=', from_date),
                    ('order_id.date_order', '<=', to_date),
                    ('order_id.company_id', '=', store.nhcl_company_id.id),
                    ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
                ]
                pos_lines = self.env['pos.order.line'].search(domain)

                for line in pos_lines:
                    tax = line.tax_ids[:1]
                    tax_name = tax.name if tax else 'No Tax'

                    taxable_amt = line.price_subtotal or 0.0
                    total_amt = line.price_subtotal_incl or 0.0
                    tax_amount = total_amt - taxable_amt

                    normal_tax_data[tax_name]['taxable_amt'] += taxable_amt
                    normal_tax_data[tax_name]['total_amt'] += total_amt
                    normal_tax_data[tax_name]['tax_amt'] += tax_amount

                    tax_rate = tax.amount if tax else 0.0
                    rounded_rate = round(tax_rate)
                    if rounded_rate in [3, 5, 12, 18, 28] or any(f"{r}%" in tax_name for r in [3, 5, 12, 18, 28]):
                        normal_tax_data[tax_name]['cgst_amt'] += tax_amount / 2
                        normal_tax_data[tax_name]['sgst_amt'] += tax_amount / 2
                    else:
                        normal_tax_data[tax_name]['igst_amt'] += tax_amount

                # ---------------------------------------------------------
                # 2. FETCH POS EXCHANGE MOVES
                # ---------------------------------------------------------
                exchange_moves = self.env['stock.move'].search([
                    ('date', '>=', from_date),
                    ('date', '<=', to_date),
                    ('state', '=', 'done'),
                    ('nhcl_exchange', '=', True),
                    ('company_id', '=', store.nhcl_company_id.id),
                ])

                for move in exchange_moves:
                    product = move.product_id
                    if not product or product.detailed_type != 'product':
                        continue

                    tax = move.nhcl_tax_ids[:1]
                    tax_name = tax.name if tax else 'No Tax'

                    exchange_taxable = -(move.nhcl_price_subtotal or 0.0)
                    exchange_total = -(move.nhcl_price_total or 0.0)
                    exchange_tax_amount = exchange_total - exchange_taxable

                    exchange_tax_data[tax_name]['taxable_amt'] += exchange_taxable
                    exchange_tax_data[tax_name]['total_amt'] += exchange_total
                    exchange_tax_data[tax_name]['tax_amt'] += exchange_tax_amount

                    tax_rate = tax.amount if tax else 0.0
                    rounded_rate = round(tax_rate)
                    if rounded_rate in [3, 5, 12, 18, 28] or any(f"{r}%" in tax_name for r in [3, 5, 12, 18, 28]):
                        exchange_tax_data[tax_name]['cgst_amt'] += exchange_tax_amount / 2
                        exchange_tax_data[tax_name]['sgst_amt'] += exchange_tax_amount / 2
                    else:
                        exchange_tax_data[tax_name]['igst_amt'] += exchange_tax_amount

            # ---------------------------------------------------------
            # 3. CREATE REPORT LINES (NORMAL & EXCHANGE SEPARATE)
            # ---------------------------------------------------------
            line_vals = []

            for tax_name, values in normal_tax_data.items():
                line_vals.append((0, 0, {
                    'pos_tax_report_id': self.id,
                    'nhcl_company_id': self.nhcl_company_id.id,
                    'tax_name': tax_name,
                    'tax_amount': values['taxable_amt'],
                    'tax_amount_total': values['total_amt'],
                    'total_tax_amount': values['tax_amt'],
                    'cgst_amount': values['cgst_amt'],
                    'sgst_amount': values['sgst_amt'],
                    'igst_amount': values['igst_amt'],
                    'from_date': self.from_date,
                    'to_date': self.to_date,
                }))

            for tax_name, values in exchange_tax_data.items():
                line_vals.append((0, 0, {
                    'pos_tax_report_id': self.id,
                    'nhcl_company_id': self.nhcl_company_id.id,
                    'tax_name': f"{tax_name} (Exchange)",
                    'tax_amount': values['taxable_amt'],
                    'tax_amount_total': values['total_amt'],
                    'total_tax_amount': values['tax_amt'],
                    'cgst_amount': values['cgst_amt'],
                    'sgst_amount': values['sgst_amt'],
                    'igst_amount': values['igst_amt'],
                    'from_date': self.from_date,
                    'to_date': self.to_date,
                }))

            self.write({
                'pos_tax_report_ids': line_vals
            })

            return {
                'type': 'ir.actions.act_window',
                'name': 'POS Tax Wise Report',
                'res_model': 'pos.tax.report.line',
                'view_mode': 'tree,pivot',
                'domain': [('pos_tax_report_id', '=', self.id)],
                'context': {
                    'default_pos_tax_report_id': self.id
                }
            }

        except Exception as e:
            print("Error in tax report:", e)
            return {'doc': []}







    def action_summery_tax_detailed_report(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Pos Tax Report',
            'res_model': 'pos.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('pos_tax_report_id', '=', self.id)],
            'context': {
                'default_pos_tax_report_id': self.id
            }
        }


class PosTaxReportline(models.TransientModel):
    _name = 'pos.tax.report.line'
    _description = 'POS Tax Report Line'

    pos_tax_report_id = fields.Many2one('pos.tax.report.wizard', 'Tax Report Line')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    tax_name = fields.Char(string='Tax Name')
    tax_amount = fields.Float(string='Amount Total (Incl)')
    tax_amount_total = fields.Float(string='Amount Total (Excl)')
    cgst_amount = fields.Float(string='CGST Amount')
    sgst_amount = fields.Float(string='SGST Amount')
    igst_amount = fields.Float(string='IGST Amount')
    total_tax_amount = fields.Float(string='Tax Amount')
    from_date = fields.Datetime(
        string="From Date"
    )

    to_date = fields.Datetime(
        string="To Date"
    )