from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclStoreAssetReport(models.Model):
    _name = 'nhcl.store.asset.report'
    _description = "nhcl store asset report"
    _rec_name = 'name'


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
    nhcl_store_asset_report_ids = fields.One2many('nhcl.store.asset.report.line', 'nhcl_asset_line_report_id')
    name = fields.Char(string='Name', default='Store Wise Asset Report')

    def nhcl_store_asset_report(self):
        for record in self:
            record.nhcl_store_asset_report_ids.unlink()

            if not record.from_date or not record.to_date:
                raise ValidationError("Please select From Date and To Date.")

            from_date = record.from_date.date()
            to_date = record.to_date.date()

            grouped_data = {}

            for store in record:

                # Search inventory counts from local DB
                inventories = self.env['cf.inventory.count'].search([
                    ('date', '>=', from_date),
                    ('date', '<=', to_date),
                    ('company_id', '=', store.nhcl_company_id.id)
                ])

                for inventory in inventories:
                    for line in inventory.line_ids:

                        asset = line.asset_id
                        if not asset:
                            continue

                        asset_name = asset.name
                        global_count = line.global_count or 0

                        key = (store.id, asset_name)
                        grouped_data[key] = grouped_data.get(key, 0) + global_count

            # Create grouped report lines
            for (nhcl_company_id, asset_name), total_amount in grouped_data.items():
                self.env['nhcl.store.asset.report.line'].sudo().create({
                    'nhcl_asset_line_report_id': record.id,
                    'nhcl_company_id': store.nhcl_company_id.id,
                    'asset_name': asset_name,
                    'global_amount': total_amount,
                })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Store Asset Report Lines',
            'res_model': 'nhcl.store.asset.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_asset_line_report_id', '=', self.id)],
            'context': {
                'default_nhcl_asset_line_report_id': self.id
            }
        }






    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_store_asset_report_ids.unlink()


    def get_excel_sheet(self):

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        bold = workbook.add_format({'bold': True})

        lines = self.nhcl_store_asset_report_ids

        # Get all asset names (columns)
        asset_names = sorted(list(set(lines.mapped('asset_name'))))

        # Header
        worksheet.write(0, 0, 'Store', bold)

        for col, asset in enumerate(asset_names, start=1):
            worksheet.write(0, col, asset, bold)

        # Prepare dictionary
        store_data = defaultdict(dict)

        for line in lines:
            store = line.nhcl_store_id.nhcl_store_name.name
            asset = line.asset_name
            store_data[store][asset] = line.global_amount

        # Write rows
        row = 1
        for store, assets in store_data.items():

            worksheet.write(row, 0, store)

            for col, asset in enumerate(asset_names, start=1):
                worksheet.write(row, col, assets.get(asset, 0))

            row += 1

        workbook.close()

        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        encoded_data = base64.b64encode(excel_data)

        attachment = self.env['ir.attachment'].create({
            'name': f'Store_Asset_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Store_Asset_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def get_asset_report_data(self):
        lines = self.sudo().nhcl_store_asset_report_ids

        asset_names = sorted(list(set(lines.mapped('asset_name'))))

        store_data = {}

        for line in lines.sudo():
            store = line.nhcl_store_id.nhcl_store_name.name
            asset = line.asset_name

            if store not in store_data:
                store_data[store] = {}

            store_data[store][asset] = line.global_amount

        return {
            'asset_names': asset_names,
            'store_data': store_data,
        }


    def action_view_store_asset_lines(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Store Asset Report Lines',
            'res_model': 'nhcl.store.asset.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_asset_line_report_id', '=', self.id)],
            'context': {
                'default_nhcl_asset_line_report_id': self.id
            }
        }


class NhclStoreAssetReportLine(models.Model):
    _name = 'nhcl.store.asset.report.line'
    _description = "nhcl store asset report line"

    nhcl_asset_line_report_id = fields.Many2one('nhcl.store.asset.report', string="Store Asset Report")
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    asset_name = fields.Char(string='Asset Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    # bill_qty = fields.Float(string="BillQty")
    # net_amount = fields.Float(string="NetAmt")
    global_amount = fields.Float(string="GlobalAmount")

