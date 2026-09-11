# -*- coding: utf-8 -*-
from odoo import fields, models


class PosSalesSummary(models.TransientModel):
    _name = 'pos.sale.summary.wizard'
    _description = "POS Sale Summary Wizard"

    start_dt = fields.Date('Start Date', required=True)
    end_dt = fields.Date('End Date', required=True)
    report_type = fields.Char('Report Type', readonly=True, default='PDF')
    only_summary = fields.Boolean('Only Summary')
    res_user_ids = fields.Many2many('res.users', default=lambda s: s.env['res.users'].search([]))
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    def sale_summary_generate_report(self):
        return self.env.ref('nhcl_bi_pos_reports.action_sales_summary_report').report_action(self)
