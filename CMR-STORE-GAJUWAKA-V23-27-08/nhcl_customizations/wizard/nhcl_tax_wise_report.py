from odoo import models,fields,api,_
import requests
from datetime import datetime, time
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
            self.pos_tax_report_ids = [(5, 0, 0)]

            line_vals = []

            for rec in self:
                pos_lines = self.env['pos.order.line'].search([
                    ('order_id.date_order', '>=', from_date),
                    ('order_id.date_order', '<=', to_date),
                    ('order_id.company_id', '=', rec.nhcl_company_id.id)
                ])


                tax_data = defaultdict(lambda: {
                    'taxable_amt': 0.0,
                    'tax_amt': 0.0,
                    'cgst_amt': 0.0,
                    'sgst_amt': 0.0,
                    'igst_amt': 0.0
                })

                for line in pos_lines:
                    taxable_amt = line.price_subtotal

                    for tax in line.tax_ids:
                        tax_rate = tax.amount or 0.0
                        tax_amount = taxable_amt * tax_rate / 100

                        tax_data[tax_rate]['taxable_amt'] += taxable_amt
                        tax_data[tax_rate]['tax_amt'] += tax_amount

                        # GST split
                        if tax_rate in [3, 5, 12, 18, 28]:
                            tax_data[tax_rate]['cgst_amt'] += tax_amount / 2
                            tax_data[tax_rate]['sgst_amt'] += tax_amount / 2
                        else:
                            tax_data[tax_rate]['igst_amt'] += tax_amount

                # Create one2many lines
                for tax_rate, values in tax_data.items():
                    line_vals.append((0, 0, {
                        'pos_tax_report_id': rec.id,
                        'nhcl_company_id': rec.nhcl_company_id.id,
                        'tax_name': f"{tax_rate}%",
                        'tax_amount': values['taxable_amt'],
                        'cgst_amount': values['cgst_amt'],
                        'sgst_amount': values['sgst_amt'],
                        'igst_amount': values['igst_amt'],
                        'total_tax_amount': values['tax_amt'],
                    }))

            # Write one2many records
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
    tax_amount = fields.Float(string='Tax Amount')
    cgst_amount = fields.Float(string='CGST Amount')
    sgst_amount = fields.Float(string='SGST Amount')
    igst_amount = fields.Float(string='IGST Amount')
    total_tax_amount = fields.Float(string='Total Tax Amount')