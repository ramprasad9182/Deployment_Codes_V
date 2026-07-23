from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BarcodeScannerSession(models.Model):
    _name = 'barcode.scanner.session'
    _description = 'Barcode Scanner Session'
    _order = "id desc"


    name = fields.Char(string="Reference", default="New", readonly=True)
    scan_date = fields.Date(string="Scan Date", default=fields.Date.context_today)
    scan_field = fields.Char(string="Scan Barcode Here", help="Scan and press Enter")

    # Matching Barcode records lines
    matched_barcode_ids = fields.Many2many(
        'stock.picking.barcode',
        string="Matched Barcodes",
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            record_count = self.search_count([])

            new_number = str(record_count + 1).zfill(4)

            vals['name'] = 'SCAN' + new_number

        return super(BarcodeScannerSession, self).create(vals)

    @api.onchange('scan_field')
    def _onchange_scan_field(self):
        if self.scan_field:
            barcode_val = self.scan_field.strip()

            # 1. Barcode system lo unda ani check
            barcode_rec = self.env['stock.picking.barcode'].search([
                ('barcode', '=', barcode_val)
            ], order='id desc', limit=1)

            if not barcode_rec:
                self.scan_field = False
                raise UserError(_("Validation Error: Barcode '%s' does not exist!") % barcode_val)

            # 2. Duplicate Check: Already scan ayyi unte record number tho error chupi
            if barcode_rec.status == 'matched':
                delivery_name = barcode_rec.stock_picking_delivery_id.name or "Unknown"
                self.scan_field = False
                raise UserError(_("Validation Error: This barcode '%s' is already scanned on record %s") % (barcode_val,
                                                                                                            delivery_name))

            # 3. Success: Status update and adding to the session list
            barcode_rec.write({'status': 'matched'})
            # self.matched_barcode_ids = [(4, barcode_rec.id)]
            self.matched_barcode_ids = [(6, 0, self.matched_barcode_ids.ids + [barcode_rec.id])]
            self.scan_field = False

