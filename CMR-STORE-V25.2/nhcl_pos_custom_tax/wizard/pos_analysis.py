# -*- coding: utf-8 -*-
################################################################################
from odoo import fields, models
from odoo.exceptions import ValidationError


class PosAnalysis(models.TransientModel):
    """
    Wizard for configuring POS analysis reports.
    """
    _name = 'pos.analysis'
    _description = 'Wizard for configuring report'

    from_date = fields.Date(
        string='From date',
        help='Start date to filter the records')
    to_date = fields.Date(string='To Date',
                          help='End date to filter the records')
    pos_session_id = fields.Many2one('pos.session',
                                     string='POS Session',
                                     help='List of pos session to generate '
                                          'report')
    partner_id = fields.Many2one('res.partner',
                                 string='Customer',
                                 help='List of partner name to generate '
                                      'report')

    def action_print_pdf(self):
        """Method to Print the report"""
        if self.from_date > self.to_date:
            raise ValidationError('Start Date must be less than End Date')
        data = {
            'from_date': self.from_date,
            'to_date': self.to_date,
            'pos_session_id': self.pos_session_id.id,
            'partner_id': self.partner_id.id,
        }
        return self.env.ref(
            'nhcl_pos_custom_tax.action_report_pos_analysis').report_action(
            self, data=data)
