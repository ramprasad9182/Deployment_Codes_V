import base64
from io import BytesIO

import openpyxl
from openpyxl.styles import Alignment
from xlwt import Font

from odoo import models, fields, api
from datetime import timedelta, datetime

from odoo.exceptions import UserError


class DayReport(models.Model):
    _name = 'day.report'
    _description = 'Day Report'

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    line_ids = fields.One2many('day.report.line', 'report_id', string="Report Lines")

    @api.onchange('from_date', 'to_date')
    def _onchange_generate_lines(self):
        if self.from_date and self.to_date and self.from_date <= self.to_date:
            self.line_ids = [(5, 0, 0)]  # Clear existing lines
            current_date = self.from_date
            lines = []

            while current_date <= self.to_date:
                # Walk-ins (only from day-type walkin.screen)
                walkin_lines = self.env['walkin.screen.line'].search([
                    ('date', '=', current_date),
                    ('walkin_screen_id.date_type', '=', 'day')
                ])
                total_walkins = sum(wl.no_of_walkins for wl in walkin_lines)

                # POS Order Lines
                pos_lines = self.env['pos.order.line'].search([
                    ('order_id.state', 'in', ['paid','done','invoiced']),
                    ('order_id.amount_total', '>', 0),
                    ('create_date', '>=', fields.Datetime.to_string(current_date)),
                    ('create_date', '<', fields.Datetime.to_string(current_date + timedelta(days=1)))
                ])
                refund_lines = self.env['pos.order.line'].search([
                    ('order_id.state', 'in', ['paid','done','invoiced']),
                    ('order_id.amount_total', '<', 0),
                    ('create_date', '>=', fields.Datetime.to_string(current_date)),
                    ('create_date', '<', fields.Datetime.to_string(current_date + timedelta(days=1)))
                ])
                orders = pos_lines.mapped('order_id')
                unique_orders = sum(orders.mapped('amount_total'))
                ref_orders = refund_lines.mapped('order_id')
                ref_unique_orders = sum(ref_orders.mapped('amount_total'))
                total_pos_orders = len(orders)
                total_amount = unique_orders + ref_unique_orders

                lines.append((0, 0, {
                    'date': current_date,
                    'walkins': total_walkins,
                    'pos_lines': total_pos_orders,
                    'total_amount': total_amount
                }))

                current_date += timedelta(days=1)

            self.line_ids = lines

    def action_export_excel(self):
        if not self.line_ids:
            raise UserError("No data to export.")

        # Send to controller with the record ID
        return {
            'type': 'ir.actions.act_url',
            'url': f'/download/day_report_excel/{self.id}',
            'target': 'self',
        }

class DayReportLine(models.Model):
    _name = 'day.report.line'
    _description = 'Day Report Line'

    report_id = fields.Many2one('day.report', string="Report")
    date = fields.Date(string="Date")
    walkins = fields.Integer(string="Walk-ins")
    pos_lines = fields.Integer(string="Count Bills")
    total_amount = fields.Float(string="Total Amount")
