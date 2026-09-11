# -*- coding: utf-8 -*-
from odoo import api, models


class ReportSaleWizard(models.AbstractModel):
    _name = 'report.nhcl_bi_pos_reports.user_wise_sales_detail_doc'
    _description = 'User Wise Sale Detail Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name(
            'nhcl_bi_pos_reports.user_wise_sales_detail_doc')
        record = {
            'doc_ids': self.env['user.wise.sales.detail.report'].search([('id', 'in', list(data["ids"]))]),
            'doc_model': report.model,
            'docs': self,
            'data': data,
        }
        return record

