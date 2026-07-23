# -*- coding: utf-8 -*-
from odoo import api, models


class ShopWiseReport(models.AbstractModel):
    _name = 'report.nhcl_bi_pos_reports.report_pos_tax_summary'
    _description = 'POS Tax Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'nhcl_bi_pos_reports.report_pos_tax_summary')
        record = {
            'doc_ids': self.env['pos.tax.summary.report'].search([('id', 'in', list(data["ids"]))]),
            'doc_model': report.model,
            'docs': self,
            'data': data,
        }
        return record
