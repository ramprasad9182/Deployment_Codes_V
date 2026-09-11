from odoo import models, fields, _
from odoo.exceptions import UserError

import base64
from io import BytesIO
import openpyxl


class MenuImportWizard(models.TransientModel):
    _name = 'menu.import.wizard'
    _description = 'Menu Import Wizard'

    user_id = fields.Many2one(
        'res.users',
        string='User'
    )
    user_ids = fields.Many2many(
        'res.users',
        string='Users',
        required=True
    )

    file = fields.Binary(
        string='Excel File',
        required=True
    )

    file_name = fields.Char()

    def action_import_menus(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("Please upload an Excel file."))

        workbook = openpyxl.load_workbook(
            BytesIO(base64.b64decode(self.file))
        )

        sheet = workbook.active

        all_menus = self.env['ir.ui.menu'].search([])

        menu_ids = []
        excel_values = []
        duplicate_names = []
        not_found = []

        for row in sheet.iter_rows(min_row=2, values_only=True):

            if not row or not row[0]:
                continue

            excel_menu = str(row[0]).strip()

            # Duplicate validation in Excel
            if excel_menu in excel_values:
                duplicate_names.append(excel_menu)
            else:
                excel_values.append(excel_menu)

            # Menu existence validation
            found_menu = all_menus.filtered(
                lambda m: (
                    m.complete_name and
                    m.complete_name.strip() == excel_menu
                )
            )

            if found_menu:
                menu_ids.append(found_menu[0].id)
            else:
                not_found.append(excel_menu)

        validation_msg = ""

        if duplicate_names:
            validation_msg += _(
                "Duplicate Menus Found In Excel:\n\n%s\n\n"
            ) % ("\n".join(sorted(set(duplicate_names))))

        if not_found:
            validation_msg += _(
                "Menus Not Found In System:\n\n%s"
            ) % ("\n".join(sorted(set(not_found))))

        if validation_msg:
            raise UserError(validation_msg)

        # Import only if all validations pass
        menu_ids = list(set(menu_ids))

        # self.user_id.write({
        #     'hide_menu_ids': [(6, 0, menu_ids)]
        # })

        self.user_ids.write({
            'hide_menu_ids': [(6, 0, menu_ids)]
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }