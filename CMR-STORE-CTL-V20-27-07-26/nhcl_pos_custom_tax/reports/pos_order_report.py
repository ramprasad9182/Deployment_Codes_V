# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>)

from odoo import fields, models


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    hours = fields.Char(readonly=True,)
    table_id = fields.Many2one('restaurant.table', string='Table', readonly=True)

    def _select(self):
        return super(PosOrderReport, self)._select() + ", to_char(date_trunc('hour', s.date_order), 'HH24:MI:SS') as hours, s.table_id as table_id"

    def _group_by(self):
        return super(PosOrderReport, self)._group_by() + ", s.table_id"
