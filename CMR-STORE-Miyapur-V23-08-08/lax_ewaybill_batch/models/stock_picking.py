from odoo import api, fields, models, _
from odoo.exceptions import UserError
from collections import defaultdict

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_create_multi_eway_bill(self):
        if not self:
            return
        
        # Check source and destination locations
        source_loc_ids = set(self.mapped('location_id.id'))
        dest_loc_ids = set(self.mapped('location_dest_id.id'))
        if len(source_loc_ids) > 1 or len(dest_loc_ids) > 1:
            raise UserError(_("Source and Destination locations must be the same for all selected pickings to create a single E-Way Bill!"))
        
        for picking in self:
            if picking.picking_type_code != 'outgoing':
                raise UserError(_("E-Way Bill can only be created for Outgoing/Delivery transfers!"))
        
        existing_eways = self.env["eway.bill.details"].search([("picking_ids", "in", self.ids)], limit=1)
        if existing_eways:
            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": existing_eways.id,
                "target": "current",
            }
        
        products_qty = {}
        for picking in self:
            for ml in picking.move_ids_without_package:
                qty = ml.quantity if picking.state == 'done' and ml.quantity else ml.product_uom_qty
                if qty <= 0:
                    continue
                products_qty[ml.product_id] = products_qty.get(ml.product_id, 0.0) + qty

        item_lines = []
        for product, qty in products_qty.items():
            item_lines.append((0, 0, {
                "product_id": product.id,
                "product_qty": qty,
                "price_unit": product.lst_price or 0.0,
            }))
        
        if not item_lines:
            raise UserError(_("No items found to create E-Way Bill."))
            
        first_picking = self[0]
        eway = self.env["eway.bill.details"].create({
            "name": first_picking.name,
            "picking_id": first_picking.id,
            "picking_ids": [(6, 0, self.ids)],
            "vendor_id": first_picking.partner_id.id,
            "item_ids": item_lines,
        })
        
        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "form",
            "res_id": eway.id,
            "target": "current",
        }


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    eway_bill_ids = fields.One2many("eway.bill.details", "batch_id", string="E-Way Bills")
    eway_bill_count = fields.Integer(string="E-Way Bill Count", compute="_compute_eway_bill_count")
    batch_transfer_type = fields.Selection(
        selection=[('advertisement', 'Advertisement'), ('direct_po', 'Direct PO'), ('ho_operation', 'HO Operation'),
                   ('sub_contract', 'Sub Contracting'), ('data_import', 'Data Import'), ('inter_state', 'Inter State'),
                   ('intra_state', 'Intra State'),
                   ('pos_exchange', 'POS Exchange'), ('others', 'Others')],
        compute='_compute_batch_transfer_type',
        string="Batch Transfer Type",
        store=True,
    )

    @api.depends('picking_ids')
    def _compute_batch_transfer_type(self):
        for rec in self:
            picking = rec.picking_ids[:1]  # First picking, if any
            rec.batch_transfer_type = picking.stock_type if picking else False

    def _compute_eway_bill_count(self):
        for batch in self:
            batch.eway_bill_count = len(batch.eway_bill_ids)

    def action_view_eway_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "tree,form",
            "domain": [("batch_id", "=", self.id)],
            "context": {"default_batch_id": self.id},
        }


    def action_create_eway_bill(self):
        self.ensure_one()

        pickings = self.picking_ids.filtered(lambda p: p.state not in ('draft', 'cancel'))
        if not pickings:
            raise UserError(_("There are no valid pickings in this batch to create an E-Way Bill."))

        # Validate source & destination
        source_loc_ids = set(pickings.mapped('location_id.id'))
        dest_loc_ids = set(pickings.mapped('location_dest_id.id'))
        if len(source_loc_ids) > 1 or len(dest_loc_ids) > 1:
            raise UserError(
                _("Source and Destination locations must be the same for all pickings in the batch to create an E-Way Bill!")
            )

        # Only outgoing pickings
        for picking in pickings:
            if picking.picking_type_code != 'outgoing':
                raise UserError(_("E-Way Bill can only be created for Outgoing/Delivery transfers!"))

        # Existing E-Way Bill
        existing_eway = self.env["eway.bill.details"].search([
            ("batch_id", "=", self.id)
        ], limit=1)

        if existing_eway:
            return {
                "type": "ir.actions.act_window",
                "res_model": "eway.bill.details",
                "view_mode": "form",
                "res_id": existing_eway.id,
                "target": "current",
            }

        # ----------------------------------------------------
        # Group by Product + HSN + Price Unit
        # ----------------------------------------------------
        grouped_lines = defaultdict(lambda: {
            'qty': 0.0,
            'price_unit': 0.0,
            'taxes': self.env['account.tax'],
        })

        for picking in pickings:
            for move in picking.move_ids_without_package:
                sale_line = move.sale_line_id
                if not sale_line:
                    continue

                qty = sale_line.qty_delivered if picking.state == 'done' else move.product_uom_qty
                if qty <= 0:
                    continue

                hsn_code = sale_line.product_id.l10n_in_hsn_code or ''

                key = (
                    sale_line.product_id.id,
                    hsn_code,
                    sale_line.price_unit,
                )

                grouped_lines[key]['qty'] += qty
                grouped_lines[key]['price_unit'] = sale_line.price_unit
                grouped_lines[key]['taxes'] |= sale_line.tax_id

        item_lines = []

        for (product_id, hsn_code, price_unit), values in grouped_lines.items():
            product = self.env['product.product'].browse(product_id)

            item_vals = {
                "name": product.display_name,
                "product_id": product.id,
                "product_qty": values['qty'],
                "price_unit": price_unit,
            }

            # Only Inter State batches should have taxes
            if self.batch_transfer_type == 'inter_state':
                item_vals["tax_ids"] = [(6, 0, values['taxes'].ids)]

            item_lines.append((0, 0, item_vals))

        if not item_lines:
            raise UserError(_("No items found to create an E-Way Bill."))

        first_picking = pickings[0]

        eway = self.env["eway.bill.details"].create({
            "name": self.name,
            "batch_id": self.id,
            "picking_id": first_picking.id,
            "picking_ids": [(6, 0, pickings.ids)],
            "vendor_id": first_picking.partner_id.id,
            "item_ids": item_lines,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "eway.bill.details",
            "view_mode": "form",
            "res_id": eway.id,
            "target": "current",
        }
