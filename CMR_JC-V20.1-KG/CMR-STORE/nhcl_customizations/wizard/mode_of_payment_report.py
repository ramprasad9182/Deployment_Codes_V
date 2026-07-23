from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz
from odoo.exceptions import ValidationError
import xmlrpc.client


from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class PosMOPReportWizard(models.TransientModel):
    _name = 'pos.mop.report.wizard'
    _description = 'POS MOP Report'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    name = fields.Char('Name',default="POS Mode Of Payment Report")
    pos_mop_report_ids = fields.One2many('pos.mop.report.line','pos_mop_report_id')
    total_cash = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cash')
    total_axis = fields.Float(compute="_compute_nhcl_show_totals", string='Total Axis')
    total_hdfc = fields.Float(compute="_compute_nhcl_show_totals", string='Total HDFC')
    total_kotak = fields.Float(compute="_compute_nhcl_show_totals", string='Total Kotak')
    total_paytm = fields.Float(compute="_compute_nhcl_show_totals", string='Total Paytm')
    total_sbi = fields.Float(compute="_compute_nhcl_show_totals", string='Total SBI')
    total_bajaj = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bajaj')
    total_mobikwik = fields.Float(compute="_compute_nhcl_show_totals", string='Total Mobikwik')
    total_cheque = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cheque')
    total_gift_voucher = fields.Float(compute="_compute_nhcl_show_totals", string='Total Gift Voucher')
    total_credit_note_settlement = fields.Float(compute="_compute_nhcl_show_totals",
                                                string='Total Credit Note Settlement')
    total_credit_note_issues = fields.Float(compute="_compute_nhcl_show_totals", string='Credit Note Issues')
    grand_total = fields.Float(compute="_compute_nhcl_show_totals", string='Grand Total')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.pos_mop_report_ids
            rec.total_cash = sum(lines.mapped('cash'))
            rec.total_axis = sum(lines.mapped('axis'))
            rec.total_hdfc = sum(lines.mapped('hdfc'))
            rec.total_kotak = sum(lines.mapped('kotak'))
            rec.total_paytm = sum(lines.mapped('paytm'))
            rec.total_sbi = sum(lines.mapped('sbi'))
            rec.total_bajaj = sum(lines.mapped('bajaj'))
            rec.total_mobikwik = sum(lines.mapped('mobikwik'))
            rec.total_cheque = sum(lines.mapped('cheque'))
            rec.total_gift_voucher = sum(lines.mapped('gift_voucher'))
            rec.total_credit_note_settlement = sum(lines.mapped('credit_note_settlement'))
            rec.total_credit_note_issues = sum(lines.mapped('credit_note_issues'))
            rec.grand_total = sum(lines.mapped('grand_total'))

    # def get_mop_payments(self):
    #     try:
    #         from_date = fields.Datetime.to_datetime(self.from_date)
    #         to_date = fields.Datetime.to_datetime(self.to_date)
    #
    #         # Clear existing lines
    #         self.pos_mop_report_ids = [(5, 0, 0)]
    #
    #         line_vals = []
    #
    #         for rec in self:
    #             # POS Payments
    #             payments = self.env['pos.payment'].search([
    #                 ('payment_date', '>=', from_date),
    #                 ('payment_date', '<=', to_date),
    #                 ('pos_order_id.company_id', '=', rec.nhcl_company_id.id)
    #             ])
    #
    #             # Credit Notes
    #             credit_moves = self.env['account.move'].search([
    #                 ('create_date', '>=', from_date),
    #                 ('create_date', '<=', to_date),
    #                 ('move_type', 'in', ['out_refund', 'in_refund']),
    #                 ('company_id', '=', rec.nhcl_company_id.id)
    #             ])
    #             credit_moves_data = self.env['stock.picking'].search([
    #                 ('date_done', '>=', from_date),
    #                 ('date_done', '<=', to_date),
    #                 ('company_id', '=', rec.nhcl_company_id.id),
    #                 ('stock_picking_type', '=', 'exchange')
    #             ])
    #
    #             # Initialize values
    #             cash = axis = hdfc = kotak = paytm = 0.0
    #             sbi = bajaj = mobikwik = cheque = 0.0
    #             gift_voucher = credit_note_settlement = 0.0
    #             credit_note_issues = 0.0
    #
    #             # Group payment methods
    #             for payment in payments:
    #                 method_name = (payment.payment_method_id.name or '').lower()
    #
    #                 if method_name == 'cash':
    #                     cash += payment.amount
    #                 elif method_name == 'axis':
    #                     axis += payment.amount
    #                 elif method_name == 'hdfc':
    #                     hdfc += payment.amount
    #                 elif method_name == 'kotak':
    #                     kotak += payment.amount
    #                 elif method_name == 'paytm':
    #                     paytm += payment.amount
    #                 elif method_name == 'sbi':
    #                     sbi += payment.amount
    #                 elif method_name == 'bajaj':
    #                     bajaj += payment.amount
    #                 elif method_name == 'mobikwik':
    #                     mobikwik += payment.amount
    #                 elif method_name == 'cheque':
    #                     cheque += payment.amount
    #                 elif method_name == 'gift voucher':
    #                     gift_voucher += payment.amount
    #
    #             # Credit Note Settlement
    #             credit_note_settlement = sum(
    #                 credit_moves.mapped('amount_total_signed')
    #             )
    #             credit_note_issues = sum(credit_moves_data.mapped('net_amount'))
    #
    #             grand_total = (
    #                     cash + axis + hdfc + kotak + paytm +
    #                     sbi + bajaj + mobikwik + cheque +
    #                     gift_voucher + credit_note_settlement
    #             )
    #
    #             line_vals.append((0, 0, {
    #                 'nhcl_company_id': rec.nhcl_company_id.id,
    #                 'cash': cash,
    #                 'axis': axis,
    #                 'hdfc': hdfc,
    #                 'kotak': kotak,
    #                 'paytm': paytm,
    #                 'sbi': sbi,
    #                 'bajaj': bajaj,
    #                 'mobikwik': mobikwik,
    #                 'cheque': cheque,
    #                 'gift_voucher': gift_voucher,
    #                 'credit_note_settlement': credit_note_settlement,
    #                 'credit_note_issues': credit_note_issues,
    #                 'grand_total': grand_total,
    #                 'pos_mop_report_id': rec.id
    #             }))
    #
    #             # Create one2many lines
    #             self.write({
    #                 'pos_mop_report_ids': line_vals
    #             })
    #
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': ' Mode Of Payment Report',
    #             'res_model': 'pos.mop.report.line',
    #             'view_mode': 'tree,pivot',
    #             'domain': [('pos_mop_report_id', '=', self.id)],
    #             'context': {
    #                 'default_pos_mop_report_id': self.id
    #             }
    #         }
    #
    #
    #
    #
    #
    #     except Exception as e:
    #         print("Error in MOP report:", e)
    #         return {'doc': []}

    def get_mop_payments(self):
        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        # clear old lines
        self.pos_mop_report_ids = [(5, 0, 0)]

        lines_to_create = []

        for rec in self:
            company_id = rec.nhcl_company_id.id

            payments = self.env['pos.payment'].search([
                ('payment_date', '>=', from_date),
                ('payment_date', '<=', to_date),
                ('pos_order_id.company_id', '=', company_id)
            ])

            mop_totals = {
                'cash': 0.0, 'axis': 0.0, 'hdfc': 0.0, 'kotak': 0.0,
                'paytm': 0.0, 'sbi': 0.0, 'bajaj': 0.0, 'mobikwik': 0.0,
                'cheque': 0.0, 'gift voucher': 0.0,
            }

            for pay in payments:
                name = (pay.payment_method_id.name or '').strip().lower()
                if name in mop_totals:
                    mop_totals[name] += pay.amount

            credit_note_settlement = sum(
                self.env['account.move'].search([
                    ('create_date', '>=', from_date),
                    ('create_date', '<=', to_date),
                    ('move_type', 'in', ['out_refund', 'in_refund']),
                    ('company_id', '=', company_id)
                ]).mapped('amount_total_signed')
            )

            cash_discount = sum(
                self.env['account.move'].search([
                    ('invoice_date', '>=', from_date),
                    ('invoice_date', '<=', to_date),
                    ('journal_id.name', '=', "Cash Discount"),
                    ('company_id', '=', company_id)
                ]).mapped('amount_total')
            )

            credit_note_issues = sum(
                self.env['stock.picking'].search([
                    ('date_done', '>=', from_date),
                    ('date_done', '<=', to_date),
                    ('company_id', '=', company_id),
                    ('stock_picking_type', '=', 'exchange')
                ]).mapped('net_amount')
            )

            grand_total = sum(mop_totals.values()) + credit_note_settlement
            excl_cash_total = grand_total - cash_discount
            lines_to_create.append({
                'pos_mop_report_id': rec.id,  # the real link
                'nhcl_company_id': company_id,
                'cash': mop_totals['cash'],
                'axis': mop_totals['axis'],
                'hdfc': mop_totals['hdfc'],
                'kotak': mop_totals['kotak'],
                'paytm': mop_totals['paytm'],
                'sbi': mop_totals['sbi'],
                'bajaj': mop_totals['bajaj'],
                'mobikwik': mop_totals['mobikwik'],
                'cheque': mop_totals['cheque'],
                'gift_voucher': mop_totals['gift voucher'],
                'credit_note_settlement': credit_note_settlement,
                'credit_note_issues': credit_note_issues,
                'grand_total': grand_total,
                'cash_discount': cash_discount,
                'excl_cash_total': excl_cash_total,
            })

        #  single bulk create
        self.env['pos.mop.report.line'].create(lines_to_create)

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Mode Of Payment Report',
            'res_model': 'pos.mop.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('pos_mop_report_id', 'in', self.ids)],
        }

    def action_summery_mop_detailed_report(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': ' Mode Of Payment Report',
            'res_model': 'pos.mop.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('pos_mop_report_id', '=', self.id)],
            'context': {
                'default_pos_mop_report_id': self.id
            }
        }


class PosMOPReportline(models.TransientModel):
    _name = 'pos.mop.report.line'
    _description = 'POS MOP Report Line'

    pos_mop_report_id = fields.Many2one('pos.mop.report.wizard', 'MOP Report Line')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    cash = fields.Float(string='Cash')
    axis = fields.Float(string='Axis')
    hdfc = fields.Float(string='HDFC')
    kotak = fields.Float(string='Kotak')
    paytm = fields.Float(string='Paytm')
    sbi = fields.Float(string='SBI')
    bajaj = fields.Float(string='Bajaj')
    mobikwik = fields.Float(string='Mobikwik')
    cheque = fields.Float(string='Cheque')
    gift_voucher = fields.Float(string='Gift Voucher')
    credit_note_settlement = fields.Float(string='Credit Note Settlement')
    credit_note_issues = fields.Float(string='Credit Note Issues')
    grand_total = fields.Float(string='Grand Total')
    cash_discount = fields.Float(string='Cash Discount')
    excl_cash_total = fields.Float(string='Excl Total')