# -*- coding: utf-8 -*-
from odoo import fields, models


class PosSalesSummary(models.TransientModel):
    _name = 'pos.top.selling.wizard'
    _description = "POS Top Selling Wizard"

    start_dt = fields.Date('Start Date', required=True)
    end_dt = fields.Date('End Date', required=True)
    report_type = fields.Char('Report Type', readonly=True, default='PDF')
    no_product = fields.Integer("Number of Products (Top)", required=True)
    top_selling = fields.Selection([('products', 'Products'), ('customers', 'Customers'), ('categories', 'Categories'),
                                    ], string="Top Selling", default="products")

    def top_selling_generate_report(self):
        return self.env.ref('nhcl_bi_pos_reports.action_top_selling_report').report_action(self)
