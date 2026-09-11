from odoo import models, fields, api
from datetime import timedelta

from odoo.exceptions import UserError, ValidationError


class HourReport(models.Model):
    _name = 'hour.report'
    _description = 'Hour Report'

    from_date = fields.Datetime(string="From Date", required=True)
    to_date = fields.Datetime(string="To Date", required=True)
    line_ids = fields.One2many('hour.report.line', 'report_id', string="Lines")

    @api.onchange('from_date', 'to_date')
    def _onchange_check_same_day(self):
        if self.from_date and self.to_date:
            if self.from_date.date() != self.to_date.date():
                raise UserError("From Date and To Date must be on the same calendar day.")

    @api.onchange('from_date', 'to_date')
    def _onchange_date_range(self):
        if self.from_date and self.to_date and self.from_date <= self.to_date:
            self.line_ids = self._prepare_hour_report_lines()

    def _prepare_hour_report_lines(self):
        self.line_ids.unlink()
        lines = []
        walkin_lines = self.env['walkin.screen.line'].search([
            ('select_date', '>=', self.from_date),
            ('select_date', '<=', self.to_date)
        ])

        for line in walkin_lines:
            from_dt = line.select_date
            to_dt = from_dt + timedelta(minutes=30)

            pos_orders = self.env['pos.order'].search([
                ('date_order', '>=', from_dt),
                ('date_order', '<', to_dt),
                ('name', 'not ilike', 'Refund'),
                ('state', 'in', ['paid','done','invoiced']),
            ])

            total_sales = sum(pos.amount_total for pos in pos_orders)

            lines.append((0, 0, {
                'date': from_dt.date(),
                'select_datetime': from_dt,
                'walkin_count': line.no_of_walkins,
                'sale_total': total_sales
            }))
        return lines

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            if rec.from_date and rec.to_date:
                rec.line_ids = rec._prepare_hour_report_lines()

        return records

    def write(self, vals):
        res = super().write(vals)
        if 'from_date' in vals or 'to_date' in vals:
            for rec in self:
                if rec.from_date and rec.to_date:
                    rec.line_ids = rec._prepare_hour_report_lines()
        return res

    def action_export_excel(self):
        if not self.line_ids:
            raise UserError("No data to export.")
        return {
            'type': 'ir.actions.act_url',
            'url': f'/download/hour_report_excel/{self.id}',
            'target': 'self',
        }

class HourReportLine(models.Model):
    _name = 'hour.report.line'
    _description = 'Hour Report Line'

    report_id = fields.Many2one('hour.report', string="Report")
    date = fields.Date(string="Date")
    select_datetime = fields.Datetime(string="Slot Time")
    walkin_count = fields.Integer(string="Walk-in Count")
    sale_total = fields.Float(string="Sale Total (Incl)")
