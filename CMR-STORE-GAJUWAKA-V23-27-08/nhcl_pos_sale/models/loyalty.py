from odoo import fields, models, _ , api
import base64
from odoo.exceptions import UserError
import io
import xlsxwriter
from odoo.exceptions import ValidationError


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def action_apply_promo(self):
        self.ensure_one()
        failed_serials = []
        offer_attribute = self.env['product.attribute'].search([
            ('name', '=', 'Offer')
        ], limit=1)

        if not offer_attribute:
            raise ValidationError("Offer attribute not found.")

        attribute_value = self.env['product.attribute.value'].search([
            ('attribute_id', '=', offer_attribute.id),
            ('name', '=', self.name)
        ], limit=1)

        if not attribute_value:
            raise ValidationError(
                "Attribute Value '%s' not found under Offer attribute." % self.name
            )

        for rule in self.rule_ids:
            for lot in rule.serial_ids:
                try:
                    lot.description_8 = attribute_value.id
                except Exception:
                    failed_serials.append(lot.name)

        if failed_serials:
            raise ValidationError(
                "Promo applied to remaining serial numbers.\n\n"
                "Could not update the following serial numbers:\n%s"
                % "\n".join(failed_serials)
            )

        return True

    def action_apply_loyalty_rules(self):
        programs = self.filtered(lambda p: p.promo_type == 'in_house')
        rules = programs.rule_ids
        if rules:
            rules.apply_loyalty_rule()
        rewards = programs.reward_ids
        for record in rewards:
            if record.discount_applicability == 'specific':
                for (i, j) in zip(range(0, len(record.program_id.rule_ids)),
                                  range(0, len(record.program_id.reward_ids))):
                    record.program_id.reward_ids[j].discount_product_ids = record.program_id.rule_ids[i].product_ids


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
