from odoo import models, fields,api
from datetime import datetime, time

from odoo.exceptions import ValidationError


class InventoryScanReport(models.Model):
    _name = "inventory.scan.report"
    _description = "Inventory Scan Report"



    plan_id = fields.Many2one(
        "stock.inventory",
        string="Plan Name",
        required=True
    )
    allowed_user_ids = fields.Many2many(
        'res.users',
        compute='_compute_allowed_users'
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        domain="[('id','in',allowed_user_ids)]"
    )

    line_ids = fields.One2many(
        "inventory.scan.report.line",
        "report_id",
        string="Scan Lines"
    )
    from_date = fields.Date(
        string="From Date"
    )

    to_date = fields.Date(
        string="To Date"
    )

    @api.depends('plan_id')
    def _compute_allowed_users(self):
        for rec in self:
            if rec.plan_id:
                rec.allowed_user_ids = rec.plan_id.scan_line_ids.mapped('user_id')
            else:
                rec.allowed_user_ids = False

    def action_get_scan_lines(self):
        for rec in self:

            # Validation 1: Plan must be selected
            if not rec.plan_id:
                raise ValidationError("Please select a Plan Name.")

            # Validation 2: Date check
            if rec.from_date and rec.to_date:
                if rec.from_date > rec.to_date:
                    raise ValidationError("From Date cannot be greater than To Date.")

            # Clear old lines
            rec.line_ids = [(5, 0, 0)]

            domain = [
                ('inventory_id', '=', rec.plan_id.id)
            ]

            if rec.user_id:
                domain.append(('user_id', '=', rec.user_id.id))
            if rec.from_date:
                from_datetime = datetime.combine(rec.from_date, time.min)
                domain.append(('scan_time', '>=', from_datetime))

            if rec.to_date:
                to_datetime = datetime.combine(rec.to_date, time.max)
                domain.append(('scan_time', '<=', to_datetime))

            scan_lines = self.env['stock.inventory.scan.line'].search(domain)
            # if not scan_lines:
            #     raise ValidationError("No scan records found for the selected filters.")

            lines = []
            for line in scan_lines:
                lines.append((0, 0, {
                    'lot_id': line.lot_id.id,
                    'user_id': line.user_id.id,
                    'scan_time': line.scan_time,
                    'count': line.count
                }))

            rec.line_ids = lines





class InventoryScanReportLine(models.Model):
    _name = "inventory.scan.report.line"
    _description = "Inventory Scan Report Line"

    report_id = fields.Many2one(
        "inventory.scan.report",
        string="Report"
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Serial / Lot No"
    )
    user_id = fields.Many2one(
        "res.users",
        string="User"
    )
    scan_time = fields.Datetime("Scan Time")
    count = fields.Integer("Cycle Count")

