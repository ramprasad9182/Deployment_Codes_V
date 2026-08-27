from odoo import fields, models, _ , api
import base64
from odoo.exceptions import UserError
import io
import xlsxwriter

class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    def action_export_filtered_barcodes(self):
        """Export all currently filtered Lot/Serial barcodes (loyalty_line_id)
        to an Excel file for download. Exports the full filtered set, not
        just the current page shown in the embedded list."""
        self.ensure_one()

        if not self.loyalty_line_id:
            raise UserError(_("There are no filtered barcodes to export. "
                              "Please click 'Get Serial No' first."))

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet('Filtered Barcodes')
        bold = workbook.add_format({'bold': True})

        headers = ['Lot/Serial', 'Barcode', 'Product']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        for row_num, line in enumerate(self.loyalty_line_id, start=1):
            worksheet.write(row_num, 0, line.lot_id.name or '')
            worksheet.write(row_num, 1, line.ref or '')
            worksheet.write(row_num, 2, line.product_id.display_name or '')

        workbook.close()
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        encoded_data = base64.b64encode(excel_data)
        filename = 'Filtered_Barcodes_%s_%s.xlsx' % (self.id, fields.Date.today())

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': filename,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
