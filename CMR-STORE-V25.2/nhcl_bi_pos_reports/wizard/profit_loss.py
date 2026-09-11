# -*- coding: utf-8 -*-
from odoo import fields, models


class PosProfitLoss(models.TransientModel):
    _name = 'pos.profit.loss.wizard'
    _description = "POS Profit Loss Wizard"

    start_dt = fields.Date('Start Date', required=True)
    end_dt = fields.Date('End Date', required=True)

    def pos_profit_loss_report(self):
        return self.env.ref('nhcl_bi_pos_reports.action_profit_loss_report').report_action(self)
