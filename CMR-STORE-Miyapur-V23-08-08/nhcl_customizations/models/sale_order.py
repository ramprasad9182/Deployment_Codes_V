from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re
from datetime import timedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    so_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('inter_state', 'Inter State'),
         ('intra_state', 'Intra State'), ('others', 'Others')],
        string='SO Type', required=True, tracking=True)
    dummy_so_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),
         ('others', 'Others')], string='Dummy SO Type', compute='_compute_nhcl_so_type')
    barcode_scanned = fields.Char(string="Scan Barcode")
    picking_document = fields.Many2one('stock.picking', string="Document", copy=False)
    operation_type = fields.Selection([('scan', 'Scan'), ('import', 'Import'), ('document', 'Document')],
                                      string="Operation Type", tracking=True, copy=False)
    transpoter_id = fields.Many2one('dev.transport.details', string='Transport by')
    entered_qty = fields.Float(string='Lot Qty', copy=False)

    mismatch_stock_ids = fields.One2many(
        'sale.mismatch.stock',
        'sale_order_id',
        string="Mismatch Stock"
    )
    nhcl_remarks = fields.Text(string="Remarks")


    transfer_type = fields.Selection(
        [('regular', 'Regular'), ('damage', 'Damage'), ('stock_mismatch', 'Stock Mismatch'), ('hpo', 'Hired Product')],
        string="Transfer Type", tracking=True, copy=False, default='regular')

    hired_product_ids = fields.One2many(
        'sale.order.hired.product',
        'sale_order_id',
        string="Hired Products"
    )
    family_id = fields.Many2one(
        'product.category',
        string='Family'
    )

    category_id = fields.Many2one(
        'product.category',
        string='Category'
    )

    class_id = fields.Many2one(
        'product.category',
        string='Class'
    )

    brick_id = fields.Many2one(
        'product.category',
        string='Brick'
    )

    has_scanned_products = fields.Boolean(
        compute='_compute_has_scanned_products'
    )
    sale_total_qty = fields.Float(compute='_compute_total_qty', store=True, string="Qty")

    @api.depends('order_line.product_uom_qty')
    def _compute_total_qty(self):
        for order in self:
            order.sale_total_qty = sum(order.order_line.mapped('product_uom_qty'))

    @api.onchange('family_id')
    def _onchange_family_id(self):
        self.category_id = False
        self.class_id = False
        self.brick_id = False

    @api.onchange('category_id')
    def _onchange_category_id(self):
        self.class_id = False
        self.brick_id = False

    @api.onchange('class_id')
    def _onchange_class_id(self):
        self.brick_id = False

    @api.depends('order_line')
    def _compute_has_scanned_products(self):
        for rec in self:
            rec.has_scanned_products = bool(rec.order_line)

    def _validate_product_hierarchy(self, product):
        categ = product.categ_id

        brick = categ
        product_class = categ.parent_id
        category = product_class.parent_id if product_class else False
        family = category.parent_id if category else False

        if self.family_id and family != self.family_id:
            raise ValidationError(
                f"{product.display_name} does not belong to selected Family."
            )

        if self.category_id and category != self.category_id:
            raise ValidationError(
                f"{product.display_name} does not belong to selected Category."
            )

        if self.class_id and product_class != self.class_id:
            raise ValidationError(
                f"{product.display_name} does not belong to selected Class."
            )

        if self.brick_id and brick != self.brick_id:
            raise ValidationError(
                f"{product.display_name} does not belong to selected Brick."
            )

    @api.onchange('barcode_scanned')
    def _onchange_barcode_scanned(self):
        if not self.so_type:
            if self.barcode_scanned:
                raise ValidationError('Please choose a So Type before scanning a barcode.')
            return
        if not self.family_id:
            raise ValidationError("Please select Family before scanning.")

        if self.barcode_scanned:
            barcode = self.barcode_scanned
            gs1_pattern = r'01(\d{14})21([A-Za-z0-9]+)'
            ean13_pattern = r'(\d{13})'
            custom_serial_pattern = r'(^(?=.*\d)[A-Za-z0-9_/\- ]+$)'
            if self.transfer_type == 'hpo':
                location = self.env.ref('stock.stock_location_stock').id

                # ---------- GS1 ----------
                if re.match(gs1_pattern, barcode):

                    product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()

                    product = self.env['product.product'].search([
                        ('barcode', '=', product_barcode)
                    ], limit=1)

                    if not product:
                        raise ValidationError(f"No product found with barcode {product_barcode}.")
                    # self._validate_product_hierarchy(product)
                    quant = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('quantity', '>', 0),
                        ('location_id', '=', location),
                        ('lot_id.name', '=', scanned_number),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)

                # ---------- CUSTOM SERIAL ----------
                elif re.match(custom_serial_pattern, barcode):

                    prefix = re.match(custom_serial_pattern, barcode).group(1)

                    quant = self.env['stock.quant'].search([
                        ('quantity', '>', 0),
                        ('location_id', '=', location),
                        ('lot_id.name', '=', prefix),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)

                else:
                    raise ValidationError("Invalid barcode for hired product.")

                if not quant:
                    raise ValidationError("No stock found for this serial.")

                lot = quant.lot_id
                self._validate_product_hierarchy(lot.product_id)

                if lot.hired_product:
                    raise ValidationError(f"Serial {lot.name} already hired.")

                existing = self.hired_product_ids.filtered(
                    lambda l: l.lot_number.id == lot.id
                )

                if existing:
                    raise ValidationError(f"Serial {lot.name} already scanned.")

                # Add to hired table
                self.hired_product_ids = [(0, 0, {
                    'product_id': lot.product_id.id,
                    'lot_number': lot.id,
                    'barcode': lot.ref,
                    'quantity': 1,
                })]

                # lot.hired_product = True

                self.barcode_scanned = False
                self.entered_qty = False
                return

            # -----------------------------
            # COMMON HELPERS
            # -----------------------------
            def search_product(barcode_field, barcode_value):
                product = self.env['product.product'].search([(barcode_field, '=', barcode_value)], limit=1)
                if not product:
                    template = self.env['product.template'].search([(barcode_field, '=', barcode_value)], limit=1)
                    if template:
                        product = template.product_variant_id
                return product

            def global_regular_lot_qty(lot, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', lot.name),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['sale', 'cancel']),
                    ('order_id.transfer_type', '=', self.transfer_type)
                ])
                return sum(sale_lines.mapped('product_uom_qty'))

            def global_regular_serial_used_orders(serial, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', serial),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['cancel']),
                    ('order_id.transfer_type', '=', self.transfer_type)
                ])
                return sale_lines.mapped('order_id.name')

            def global_damage_serial_used_orders(serial, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', serial),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['cancel']), ('order_id.transfer_type', '=', 'damage')
                ])
                return sale_lines.mapped('order_id.name')

            def global_damage_lot_qty(lot, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', lot.name),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['cancel']), ('order_id.transfer_type', '=', 'damage')
                ])
                return sum(sale_lines.mapped('product_uom_qty'))

            def get_existing_line(lot, sale_serial_type):
                return self.order_line.filtered(
                    lambda l: l.lot_ids and lot.id in l.lot_ids.ids and l.sale_serial_type == sale_serial_type
                )

            existing_order_line_cmds = [(4, line.id) for line in self.order_line]

            location = False
            if self.transfer_type == 'regular':
                location = self.env.ref('stock.stock_location_stock').id

            elif self.transfer_type == 'damage':
                location_rec = self.env['stock.location'].search(
                    [('name', 'like', '%-DM')],
                    limit=1
                )
                if not location_rec:
                    raise ValidationError("Damage location (-DM) not found.")
                location = location_rec.id
            elif self.transfer_type == 'stock_mismatch':
                location = self.env.ref('stock.stock_location_stock').id
            elif self.transfer_type == 'hpo':  # ADD THIS
                location = self.env.ref('stock.stock_location_stock').id
            if not location:
                raise ValidationError("Invalid transfer type. Location could not be determined.")
            product = False
            if self.transfer_type == 'stock_mismatch':
                product = self.env['product.product'].search([('name', '=', 'MISMATCHED')], limit=1)
                if not product:
                    raise ValidationError("Product not found with name 'MISMATCHED'.")
            # ----------------------------------------------------------------------------
            # GS1 BARCODE
            # ----------------------------------------------------------------------------
            if re.match(gs1_pattern, barcode) and self.transfer_type != 'stock_mismatch':
                product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
                product = search_product('barcode', product_barcode)
                if not product:
                    raise ValidationError(f"No product found with barcode {product_barcode}.")
                self._validate_product_hierarchy(product)
                if product.tracking not in ('serial', 'lot'):
                    raise ValidationError(f'Product {product.display_name} must have serial or lot tracking.')
                lots = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('quantity', '>', 0),
                    ('location_id', '=', location),
                    ('lot_id.name', '=', scanned_number),
                    ('lot_id.type_product', '=', 'un_brand'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)
                lot = lots.lot_id
                if not lot:
                    raise ValidationError(f'No lot/serial number found for {scanned_number}.')
                if lot.rs_price <= 0.0:
                    raise ValidationError("Some serial numbers are missing landed cost.")
                sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                # ---------------- SERIAL ----------------
                if product.tracking == 'serial':
                    if self.entered_qty and self.entered_qty > 1:
                        raise ValidationError("Serial Product: Qty must be 1.")

                    existing_orders = global_regular_serial_used_orders(scanned_number, sale_serial_type)
                    if existing_orders:
                        raise ValidationError(
                            f"Serial {scanned_number} already used in: {', '.join(set(existing_orders))}")

                    if scanned_number in self.order_line.filtered(
                            lambda l: l.sale_serial_type == sale_serial_type).mapped('lot_ids.name'):
                        raise ValidationError(f"Serial number {scanned_number} is already used in this order.")

                    qty = 1
                    new_line = (0, 0, {
                        'product_id': product.id,
                        'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                        'class_id': lot.product_id.categ_id.parent_id.id,
                        'brick_id': lot.product_id.categ_id.id,
                        'product_uom_qty': qty,
                        'lot_ids': [(4, lot.id)],
                        'branded_barcode': lot.ref,
                        'type_product': lot.type_product,
                        'price_unit': lot.cost_price,
                        'sale_serial_type': sale_serial_type,
                    })
                    lot.is_uploaded = True
                    self.order_line = [new_line] + existing_order_line_cmds
                # ---------------- LOT ----------------
                else:
                    # UNIVERSAL LOT MERGING LOGIC
                    if not self.entered_qty or self.entered_qty <= 0:
                        raise ValidationError("Enter a valid quantity for lot tracked product.")

                    requested_qty = self.entered_qty
                    available_stock = sum(lots.mapped('quantity'))
                    global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
                    existing_line = get_existing_line(lot, sale_serial_type)
                    line_used_qty = sum(existing_line.mapped('product_uom_qty'))
                    total_after_scan = line_used_qty + requested_qty

                    # EXCEED VALIDATION
                    if global_used_qty + requested_qty > available_stock:
                        raise ValidationError(
                            f"Qty exceeds available stock for lot {lot.name}. "
                            f"Available: {available_stock - global_used_qty}"
                        )
                    if total_after_scan > available_stock:
                        raise ValidationError(
                            f"Qty exceeds available stock for lot {lot.name}. ")

                    if existing_line:
                        existing_line.product_uom_qty = total_after_scan
                        existing_line.price_unit = lot.cost_price
                    else:
                        new_line = (0, 0, {
                            'product_id': lot.product_id.id,
                            'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                            'class_id': lot.product_id.categ_id.parent_id.id,
                            'brick_id': lot.product_id.categ_id.id,
                            'product_uom_qty': requested_qty,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': sale_serial_type
                        })
                        self.order_line = [new_line] + existing_order_line_cmds
                    lot.is_uploaded = True
            elif re.match(gs1_pattern, barcode) and self.transfer_type == 'stock_mismatch':
                product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()

                last_scanned = self.env['last.scanned.serial.number'].search([
                    ('stock_serial', '=', scanned_number),
                    ('type_product', '=', 'un_brand'),
                ], limit=1)

                if not last_scanned:
                    raise ValidationError(f'No lot/serial number found for {scanned_number}.')
                available_qty = last_scanned.stock_qty
                #  GLOBAL VALIDATION
                used_count = self.env['sale.mismatch.stock'].search_count([
                    ('serial_number', '=', scanned_number),
                    ('sale_order_id.state', '!=', 'cancel'),
                ])
                current_count = len(self.mismatch_stock_ids.filtered(lambda l: l.serial_number == scanned_number))

                if (used_count + current_count) >= available_qty:
                    raise ValidationError(
                        f"Serial {scanned_number} already used maximum allowed ({available_qty})."
                    )
                # ---------------- ADD MISMATCH LINE ----------------
                self.mismatch_stock_ids = [(0, 0, {
                    'serial_number': scanned_number,
                    'barcode': barcode,
                    'document_name': self.name,
                    'stock_qty': available_qty,
                })]

                # ---------------- UPDATE SINGLE SO LINE ----------------
                total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))

                existing_line = self.order_line.filtered(
                    lambda l: l.product_id.id == product.id
                )

                if existing_line:
                    existing_line.product_uom_qty = total_mismatch_qty
                else:
                    self.order_line = [(0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': total_mismatch_qty,
                        'price_unit': 1,
                    })]

            # ----------------------------------------------------------------------------
            # EAN13 BARCODE
            # ----------------------------------------------------------------------------
            elif re.match(ean13_pattern, barcode) and self.transfer_type == 'regular':
                ean13_barcode = re.match(ean13_pattern, barcode).group(1)
                lots = self.env['stock.quant'].search([
                    ('lot_id.ref', '=', ean13_barcode),
                    ('quantity', '>', 0),
                    ('location_id', '=', location),
                    ('lot_id.type_product', '=', 'brand'),
                    ('company_id', '=', self.company_id.id)
                ])
                if not lots:
                    raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
                product = lots[0].product_id
                self._validate_product_hierarchy(product)
                if product.tracking not in ('serial', 'lot'):
                    raise ValidationError("Product must be tracked (serial or lot).")
                # ---------------- SERIAL ----------------
                if product.tracking == 'serial':
                    used_names = set(self.order_line.mapped('lot_ids.name'))
                    available_lot = None
                    for lot in lots.lot_id:
                        sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                        if lot.name in used_names:
                            continue
                        existing_orders = global_regular_serial_used_orders(lot.name, sale_serial_type)
                        if existing_orders:
                            continue
                        available_lot = lot
                        break
                    if not available_lot:
                        raise ValidationError("All serials for this product are already used.")

                    if available_lot.rs_price <= 0.0:
                        raise ValidationError("Some serial numbers are missing landed cost.")

                    new_line = (0, 0, {
                        'product_id': product.id,
                        'family_id': available_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': available_lot.product_id.categ_id.parent_id.parent_id.id,
                        'class_id': available_lot.product_id.categ_id.parent_id.id,
                        'brick_id': available_lot.product_id.categ_id.id,
                        'product_uom_qty': 1,
                        'lot_ids': [(4, available_lot.id)],
                        'branded_barcode': available_lot.ref,
                        'type_product': available_lot.type_product,
                        'price_unit': available_lot.cost_price,
                        'sale_serial_type': sale_serial_type
                    })
                    available_lot.is_uploaded = True
                    self.order_line = [new_line] + existing_order_line_cmds

                # ---------------- LOT (MERGING) ----------------
                else:
                    remaining_qty = self.entered_qty
                    if not remaining_qty or remaining_qty <= 0:
                        raise ValidationError("Enter a valid quantity.")
                    used_names = set(self.order_line.mapped('lot_ids.name'))
                    for quant in lots:
                        if remaining_qty <= 0:
                            break
                        lot = quant.lot_id
                        sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                        available_stock = quant.quantity
                        global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
                        existing_line = get_existing_line(lot, sale_serial_type)
                        line_used_qty = sum(existing_line.mapped('product_uom_qty'))
                        effective_available = available_stock - global_used_qty - existing_line.product_uom_qty
                        if effective_available <= 0:
                            continue
                        consume = min(remaining_qty, effective_available)
                        # Merge or create
                        if existing_line:
                            existing_line.product_uom_qty = line_used_qty + consume
                            existing_line.price_unit = lot.cost_price
                        else:
                            new_line = (0, 0, {
                                'product_id': product.id,
                                'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                                'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                                'class_id': lot.product_id.categ_id.parent_id.id,
                                'brick_id': lot.product_id.categ_id.id,
                                'product_uom_qty': consume,
                                'lot_ids': [(4, lot.id)],
                                'branded_barcode': lot.ref,
                                'type_product': lot.type_product,
                                'price_unit': lot.cost_price,
                                'sale_serial_type': sale_serial_type
                            })
                            self.order_line = [new_line] + existing_order_line_cmds
                        lot.is_uploaded = True
                        remaining_qty -= consume
                    if remaining_qty > 0:
                        raise ValidationError(
                            f"Only {self.entered_qty - remaining_qty} qty available. "
                            f"Missing {remaining_qty} qty."
                        )
            elif re.match(ean13_pattern, barcode) and self.transfer_type == 'damage':
                ean13_barcode = re.match(ean13_pattern, barcode).group(1)
                lots = self.env['stock.quant'].search([
                    ('lot_id.ref', '=', ean13_barcode),
                    ('quantity', '>', 0),
                    ('location_id', '=', location),
                    ('lot_id.type_product', '=', 'brand'),
                    ('company_id', '=', self.company_id.id)
                ])
                if not lots:
                    raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
                product = lots[0].product_id
                self._validate_product_hierarchy(product)
                if product.tracking not in ('serial', 'lot'):
                    raise ValidationError("Product must be tracked (serial or lot).")
                # ---------------- SERIAL ----------------
                if product.tracking == 'serial':
                    used_names = set(self.order_line.mapped('lot_ids.name'))
                    available_lot = None
                    for lot in lots.lot_id:
                        sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                        if lot.name in used_names:
                            continue
                        existing_orders = global_damage_serial_used_orders(lot.name, sale_serial_type)
                        if existing_orders:
                            continue
                        available_lot = lot
                        break
                    if not available_lot:
                        raise ValidationError("All serials for this product are already used.")

                    if available_lot.rs_price <= 0.0:
                        raise ValidationError("Some serial numbers are missing landed cost.")

                    new_line = (0, 0, {
                        'product_id': product.id,
                        'family_id': available_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': available_lot.product_id.categ_id.parent_id.parent_id.id,
                        'class_id': available_lot.product_id.categ_id.parent_id.id,
                        'brick_id': available_lot.product_id.categ_id.id,
                        'product_uom_qty': 1,
                        'lot_ids': [(4, available_lot.id)],
                        'branded_barcode': available_lot.ref,
                        'type_product': available_lot.type_product,
                        'price_unit': available_lot.cost_price,
                        'sale_serial_type': sale_serial_type
                    })
                    available_lot.is_uploaded = True
                    self.order_line = [new_line] + existing_order_line_cmds

                # ---------------- LOT (MERGING) ----------------
                else:
                    remaining_qty = self.entered_qty
                    if not remaining_qty or remaining_qty <= 0:
                        raise ValidationError("Enter a valid quantity.")
                    used_names = set(self.order_line.mapped('lot_ids.name'))
                    for quant in lots:
                        if remaining_qty <= 0:
                            break
                        lot = quant.lot_id
                        sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                        available_stock = quant.quantity
                        global_used_qty = global_damage_lot_qty(lot, sale_serial_type)
                        existing_line = get_existing_line(lot, sale_serial_type)
                        line_used_qty = sum(existing_line.mapped('product_uom_qty'))
                        effective_available = available_stock - global_used_qty - existing_line.product_uom_qty
                        if effective_available <= 0:
                            continue
                        consume = min(remaining_qty, effective_available)
                        # Merge or create
                        if existing_line:
                            existing_line.product_uom_qty = line_used_qty + consume
                            existing_line.price_unit = lot.cost_price
                        else:
                            new_line = (0, 0, {
                                'product_id': product.id,
                                'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                                'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                                'class_id': lot.product_id.categ_id.parent_id.id,
                                'brick_id': lot.product_id.categ_id.id,
                                'product_uom_qty': consume,
                                'lot_ids': [(4, lot.id)],
                                'branded_barcode': lot.ref,
                                'type_product': lot.type_product,
                                'price_unit': lot.cost_price,
                                'sale_serial_type': sale_serial_type
                            })
                            self.order_line = [new_line] + existing_order_line_cmds
                        lot.is_uploaded = True
                        remaining_qty -= consume
                    if remaining_qty > 0:
                        raise ValidationError(
                            f"Only {self.entered_qty - remaining_qty} qty available. "
                            f"Missing {remaining_qty} qty."
                        )
            elif re.match(ean13_pattern, barcode) and self.transfer_type == 'stock_mismatch':
                ean13_barcode = re.match(ean13_pattern, barcode).group(1)

                last_scanned = self.env['last.scanned.serial.number'].search([
                    ('stock_product_barcode', '=', ean13_barcode),
                    ('type_product', '=', 'brand'),
                ], limit=1)

                if not last_scanned:
                    raise ValidationError(f'No lot/serial number found for {ean13_barcode}.')
                available_qty = last_scanned.stock_qty
                # 🔴 GLOBAL VALIDATION
                used_count = self.env['sale.mismatch.stock'].search_count([
                    ('barcode', '=', ean13_barcode),
                    ('sale_order_id.state', '!=', 'cancel'),
                ])
                current_count = len(self.mismatch_stock_ids.filtered(lambda l: l.barcode == ean13_barcode))

                if (used_count + current_count) >= available_qty:
                    raise ValidationError(
                        f"Serial {ean13_barcode} already used maximum allowed ({available_qty})."
                    )
                # ---------------- ADD MISMATCH LINE ----------------
                self.mismatch_stock_ids = [(0, 0, {
                    'serial_number': ean13_barcode,
                    'barcode': ean13_barcode,
                    'document_name': self.name,
                    'stock_qty': available_qty,
                })]

                # ---------------- UPDATE SINGLE SO LINE ----------------
                total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))

                existing_line = self.order_line.filtered(
                    lambda l: l.product_id.id == product.id
                )

                if existing_line:
                    existing_line.product_uom_qty = total_mismatch_qty
                else:
                    self.order_line = [(0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': total_mismatch_qty,
                        'price_unit': 1,
                    })]
            # ----------------------------------------------------------------------------
            # CUSTOM SERIAL BARCODE
            # ----------------------------------------------------------------------------
            elif re.match(custom_serial_pattern, barcode) and self.transfer_type != 'stock_mismatch':
                prefix = re.match(custom_serial_pattern, barcode).group(1)
                Quant = self.env['stock.quant']

                # ---------------- UNBRANDED (UNCHANGED) ----------------
                lots = Quant.search([
                    ('quantity', '>', 0),
                    ('company_id', '=', self.company_id.id),
                    ('location_id', '=', location),
                    ('lot_id.name', '=', prefix),
                    ('lot_id.type_product', '=', 'un_brand'),
                ])

                is_branded = False
                if not lots:
                    # ---------------- BRANDED ----------------
                    lots = Quant.search([
                        ('quantity', '>', 0),
                        ('company_id', '=', self.company_id.id),
                        ('location_id', '=', location),
                        ('lot_id.ref', '=', prefix),
                        ('lot_id.type_product', '=', 'brand'),
                    ])
                    is_branded = True

                if not lots:
                    raise ValidationError(f"No lots found for custom barcode {prefix}")

                selected_lot = None
                qty = 0

                # Used serials in current order
                used_serials = set(
                    self.order_line.mapped('lot_ids.name')
                )

                # FIFO: always pick lowest ID first
                for lot in lots.lot_id.sorted(key=lambda l: l.id):
                    product = lot.product_id
                    self._validate_product_hierarchy(product)
                    sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'

                    # ---------------- SERIAL ----------------
                    if product.tracking == 'serial':

                        if self.entered_qty and self.entered_qty > 1:
                            raise ValidationError("Serial product: Qty must be 1.")

                        # 🔴 UNBRANDED → OLD BEHAVIOR (STRICT)
                        if not is_branded:
                            if lot.name in used_serials:
                                raise ValidationError(
                                    f"Serial {lot.name} already used in this order."
                                )
                            existing_orders = global_regular_serial_used_orders(
                                lot.name, sale_serial_type
                            )
                            if existing_orders:
                                raise ValidationError(
                                    f"Serial {lot.name} already used in: {', '.join(set(existing_orders))}"
                                )
                            selected_lot = lot
                            qty = 1
                            break

                        # 🟢 BRANDED → NEW FIFO BEHAVIOR
                        if lot.name in used_serials:
                            continue

                        existing_orders = global_regular_serial_used_orders(
                            lot.name, sale_serial_type
                        )
                        if existing_orders:
                            continue

                        # First free serial found
                        selected_lot = lot
                        qty = 1
                        break

                    # ---------------- LOT (UNCHANGED) ----------------
                    else:
                        if not self.entered_qty or self.entered_qty <= 0:
                            raise ValidationError("Enter a valid quantity.")

                        requested_qty = self.entered_qty
                        available_stock = sum(lots.mapped('quantity'))
                        global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
                        existing_line = get_existing_line(lot, sale_serial_type)
                        line_used_qty = sum(existing_line.mapped('product_uom_qty'))
                        total_after_scan = line_used_qty + requested_qty

                        if global_used_qty + requested_qty > available_stock:
                            raise ValidationError(
                                f"Qty exceeds available stock for lot {lot.name}. "
                                f"Available: {available_stock - global_used_qty}"
                            )

                        if total_after_scan + global_used_qty > available_stock:
                            raise ValidationError(
                                f"Qty exceeds available stock for lot {lot.name}."
                            )

                        selected_lot = lot
                        qty = requested_qty
                        break

                if not selected_lot:
                    raise ValidationError(
                        f"No available serial/lot found for barcode {prefix}"
                    )

                if selected_lot.rs_price <= 0.0:
                    raise ValidationError("Some serial numbers are missing landed cost.")

                # ---------------- MERGE / CREATE ----------------
                existing_line = get_existing_line(selected_lot, sale_serial_type)
                if existing_line:
                    existing_line.product_uom_qty += qty
                    existing_line.price_unit = selected_lot.cost_price
                else:
                    new_line = (0, 0, {
                        'product_id': selected_lot.product_id.id,
                        'family_id': selected_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': selected_lot.product_id.categ_id.parent_id.parent_id.id,
                        'class_id': selected_lot.product_id.categ_id.parent_id.id,
                        'brick_id': selected_lot.product_id.categ_id.id,
                        'product_uom_qty': qty,
                        'lot_ids': [(4, selected_lot.id)],
                        'branded_barcode': selected_lot.ref,
                        'type_product': selected_lot.type_product,
                        'price_unit': selected_lot.cost_price,
                        'sale_serial_type': sale_serial_type
                    })
                    self.order_line = [new_line] + existing_order_line_cmds

                selected_lot.is_uploaded = True

            elif re.match(custom_serial_pattern, barcode) and self.transfer_type == 'stock_mismatch':
                match = re.match(custom_serial_pattern, barcode)
                prefix = match.group(1)
                SerialModel = self.env['last.scanned.serial.number']
                # -------------------------------------------------
                # 1️⃣ FIND RECORD (Try un_brand first, then brand)
                # -------------------------------------------------
                last_scanned = SerialModel.search([
                    ('stock_serial', '=', prefix),
                    ('type_product', '=', 'un_brand'),
                ], limit=1)
                if not last_scanned:
                    last_scanned = SerialModel.search([
                        ('stock_serial', '=', prefix),
                        ('type_product', '=', 'brand'), ], limit=1)

                if not last_scanned:
                    raise ValidationError(f'No lot/serial number found for {prefix}.')

                available_qty = last_scanned.stock_qty
                # -------------------------------------------------
                # 2️⃣ GLOBAL DUPLICATE VALIDATION
                # -------------------------------------------------
                key_field = 'serial_number' if last_scanned.type_product == 'un_brand' else 'barcode'
                key_value = prefix if key_field == 'serial_number' else barcode
                used_count = self.env['sale.mismatch.stock'].search_count([
                    (key_field, '=', key_value),
                    ('sale_order_id.state', '!=', 'cancel'),
                    ('sale_order_id', '!=', self.id),
                ])
                if key_field == 'serial_number':
                    used_current_count = len(
                        self.mismatch_stock_ids.filtered(
                            lambda l: l.serial_number == key_value
                        )
                    )
                else:
                    used_current_count = len(
                        self.mismatch_stock_ids.filtered(
                            lambda l: l.barcode == key_value
                        )
                    )
                if (used_count + used_current_count) >= available_qty:
                    raise ValidationError(
                        f"{key_value} already used maximum allowed ({available_qty})."
                    )
                # -------------------------------------------------
                # 3️⃣ ADD MISMATCH LINE
                # -------------------------------------------------
                self.mismatch_stock_ids = [(0, 0, {
                    'serial_number': prefix,
                    'barcode': barcode,
                    'document_name': self.name,
                    'stock_qty': available_qty,

                })]
                # -------------------------------------------------
                # 4️⃣ UPDATE SINGLE SALE ORDER LINE
                # -------------------------------------------------
                total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))
                existing_line = self.order_line.filtered(
                    lambda l: l.product_id.id == product.id
                )
                if existing_line:
                    existing_line.product_uom_qty = total_mismatch_qty
                else:
                    self.order_line = [(0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': total_mismatch_qty,
                        'price_unit': 1,
                    })]

            else:
                raise ValidationError('Invalid barcode format.')

            self.barcode_scanned = False
            self.entered_qty = False

    # @api.onchange('barcode_scanned')
    # def _onchange_barcode_scanned(self):
    #     if not self.so_type:
    #         if self.barcode_scanned:
    #             raise ValidationError('Please choose a So Type before scanning a barcode.')
    #         return
    #
    #     if self.barcode_scanned:
    #         barcode = self.barcode_scanned
    #         gs1_pattern = r'01(\d{14})21([A-Za-z0-9]+)'
    #         ean13_pattern = r'(\d{13})'
    #         custom_serial_pattern = r'(^(?=.*\d)[A-Za-z0-9_/\- ]+$)'
    #         if self.transfer_type == 'hpo':
    #             location = self.env.ref('stock.stock_location_stock').id
    #
    #             # ---------- GS1 ----------
    #             if re.match(gs1_pattern, barcode):
    #
    #                 product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
    #
    #                 product = self.env['product.product'].search([
    #                     ('barcode', '=', product_barcode)
    #                 ], limit=1)
    #
    #                 if not product:
    #                     raise ValidationError(f"No product found with barcode {product_barcode}.")
    #
    #                 quant = self.env['stock.quant'].search([
    #                     ('product_id', '=', product.id),
    #                     ('quantity', '>', 0),
    #                     ('location_id', '=', location),
    #                     ('lot_id.name', '=', scanned_number),
    #                     ('company_id', '=', self.company_id.id)
    #                 ], limit=1)
    #
    #             # ---------- CUSTOM SERIAL ----------
    #             elif re.match(custom_serial_pattern, barcode):
    #
    #                 prefix = re.match(custom_serial_pattern, barcode).group(1)
    #
    #                 quant = self.env['stock.quant'].search([
    #                     ('quantity', '>', 0),
    #                     ('location_id', '=', location),
    #                     ('lot_id.name', '=', prefix),
    #                     ('company_id', '=', self.company_id.id)
    #                 ], limit=1)
    #
    #             else:
    #                 raise ValidationError("Invalid barcode for hired product.")
    #
    #             if not quant:
    #                 raise ValidationError("No stock found for this serial.")
    #
    #             lot = quant.lot_id
    #
    #             if lot.hired_product:
    #                 raise ValidationError(f"Serial {lot.name} already hired.")
    #
    #             existing = self.hired_product_ids.filtered(
    #                 lambda l: l.lot_number.id == lot.id
    #             )
    #
    #             if existing:
    #                 raise ValidationError(f"Serial {lot.name} already scanned.")
    #
    #             # Add to hired table
    #             self.hired_product_ids = [(0, 0, {
    #                 'product_id': lot.product_id.id,
    #                 'lot_number': lot.id,
    #                 'barcode': lot.ref,
    #                 'quantity': 1,
    #             })]
    #
    #             # lot.hired_product = True
    #
    #             self.barcode_scanned = False
    #             self.entered_qty = False
    #             return
    #
    #         # -----------------------------
    #         # COMMON HELPERS
    #         # -----------------------------
    #         def search_product(barcode_field, barcode_value):
    #             product = self.env['product.product'].search([(barcode_field, '=', barcode_value)], limit=1)
    #             if not product:
    #                 template = self.env['product.template'].search([(barcode_field, '=', barcode_value)], limit=1)
    #                 if template:
    #                     product = template.product_variant_id
    #             return product
    #
    #         def global_regular_lot_qty(lot, current_type):
    #             sale_lines = self.env['sale.order.line'].search([
    #                 ('lot_ids.name', '=', lot.name),
    #                 ('company_id', '=', self.env.company.id),
    #                 ('sale_serial_type', '=', current_type),
    #                 ('order_id.state', 'not in', ['sale', 'cancel']),
    #                 ('order_id.transfer_type', '=', self.transfer_type)
    #             ])
    #             return sum(sale_lines.mapped('product_uom_qty'))
    #
    #         def global_regular_serial_used_orders(serial, current_type):
    #             sale_lines = self.env['sale.order.line'].search([
    #                 ('lot_ids.name', '=', serial),
    #                 ('company_id', '=', self.env.company.id),
    #                 ('sale_serial_type', '=', current_type),
    #                 ('order_id.state', 'not in', ['cancel']),
    #                 ('order_id.transfer_type', '=', self.transfer_type)
    #             ])
    #             return sale_lines.mapped('order_id.name')
    #
    #         def global_damage_serial_used_orders(serial, current_type):
    #             sale_lines = self.env['sale.order.line'].search([
    #                 ('lot_ids.name', '=', serial),
    #                 ('company_id', '=', self.env.company.id),
    #                 ('sale_serial_type', '=', current_type),
    #                 ('order_id.state', 'not in', ['cancel']), ('order_id.transfer_type', '=', 'damage')
    #             ])
    #             return sale_lines.mapped('order_id.name')
    #
    #         def global_damage_lot_qty(lot, current_type):
    #             sale_lines = self.env['sale.order.line'].search([
    #                 ('lot_ids.name', '=', lot.name),
    #                 ('company_id', '=', self.env.company.id),
    #                 ('sale_serial_type', '=', current_type),
    #                 ('order_id.state', 'not in', ['cancel']), ('order_id.transfer_type', '=', 'damage')
    #             ])
    #             return sum(sale_lines.mapped('product_uom_qty'))
    #
    #         def get_existing_line(lot, sale_serial_type):
    #             return self.order_line.filtered(
    #                 lambda l: l.lot_ids and lot.id in l.lot_ids.ids and l.sale_serial_type == sale_serial_type
    #             )
    #
    #         existing_order_line_cmds = [(4, line.id) for line in self.order_line]
    #
    #         location = False
    #         if self.transfer_type == 'regular':
    #             location = self.env.ref('stock.stock_location_stock').id
    #
    #         elif self.transfer_type == 'damage':
    #             location_rec = self.env['stock.location'].search(
    #                 [('name', 'like', '%-DM')],
    #                 limit=1
    #             )
    #             if not location_rec:
    #                 raise ValidationError("Damage location (-DM) not found.")
    #             location = location_rec.id
    #         elif self.transfer_type == 'stock_mismatch':
    #             location = self.env.ref('stock.stock_location_stock').id
    #         elif self.transfer_type == 'hpo':  # ADD THIS
    #             location = self.env.ref('stock.stock_location_stock').id
    #         if not location:
    #             raise ValidationError("Invalid transfer type. Location could not be determined.")
    #         product = False
    #         if self.transfer_type == 'stock_mismatch':
    #             product = self.env['product.product'].search([('name', '=', 'MISMATCHED')], limit=1)
    #             if not product:
    #                 raise ValidationError("Product not found with name 'MISMATCHED'.")
    #         # ----------------------------------------------------------------------------
    #         # GS1 BARCODE
    #         # ----------------------------------------------------------------------------
    #         if re.match(gs1_pattern, barcode) and self.transfer_type != 'stock_mismatch':
    #             product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
    #             product = search_product('barcode', product_barcode)
    #             if not product:
    #                 raise ValidationError(f"No product found with barcode {product_barcode}.")
    #             if product.tracking not in ('serial', 'lot'):
    #                 raise ValidationError(f'Product {product.display_name} must have serial or lot tracking.')
    #             lots = self.env['stock.quant'].search([
    #                 ('product_id', '=', product.id),
    #                 ('quantity', '>', 0),
    #                 ('location_id', '=', location),
    #                 ('lot_id.name', '=', scanned_number),
    #                 ('lot_id.type_product', '=', 'un_brand'),
    #                 ('company_id', '=', self.company_id.id)
    #             ], limit=1)
    #             lot = lots.lot_id
    #             if not lot:
    #                 raise ValidationError(f'No lot/serial number found for {scanned_number}.')
    #             if lot.rs_price <= 0.0:
    #                 raise ValidationError("Some serial numbers are missing landed cost.")
    #             sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #             # ---------------- SERIAL ----------------
    #             if product.tracking == 'serial':
    #                 if self.entered_qty and self.entered_qty > 1:
    #                     raise ValidationError("Serial Product: Qty must be 1.")
    #
    #                 existing_orders = global_regular_serial_used_orders(scanned_number, sale_serial_type)
    #                 if existing_orders:
    #                     raise ValidationError(
    #                         f"Serial {scanned_number} already used in: {', '.join(set(existing_orders))}")
    #
    #                 if scanned_number in self.order_line.filtered(
    #                         lambda l: l.sale_serial_type == sale_serial_type).mapped('lot_ids.name'):
    #                     raise ValidationError(f"Serial number {scanned_number} is already used in this order.")
    #
    #                 qty = 1
    #                 new_line = (0, 0, {
    #                     'product_id': product.id,
    #                     'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                     'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
    #                     'class_id': lot.product_id.categ_id.parent_id.id,
    #                     'brick_id': lot.product_id.categ_id.id,
    #                     'product_uom_qty': qty,
    #                     'lot_ids': [(4, lot.id)],
    #                     'branded_barcode': lot.ref,
    #                     'type_product': lot.type_product,
    #                     'price_unit': lot.cost_price,
    #                     'sale_serial_type': sale_serial_type,
    #                 })
    #                 lot.is_uploaded = True
    #                 self.order_line = [new_line] + existing_order_line_cmds
    #             # ---------------- LOT ----------------
    #             else:
    #                 # UNIVERSAL LOT MERGING LOGIC
    #                 if not self.entered_qty or self.entered_qty <= 0:
    #                     raise ValidationError("Enter a valid quantity for lot tracked product.")
    #
    #                 requested_qty = self.entered_qty
    #                 available_stock = sum(lots.mapped('quantity'))
    #                 global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
    #                 existing_line = get_existing_line(lot, sale_serial_type)
    #                 line_used_qty = sum(existing_line.mapped('product_uom_qty'))
    #                 total_after_scan = line_used_qty + requested_qty
    #
    #                 # EXCEED VALIDATION
    #                 if global_used_qty + requested_qty > available_stock:
    #                     raise ValidationError(
    #                         f"Qty exceeds available stock for lot {lot.name}. "
    #                         f"Available: {available_stock - global_used_qty}"
    #                     )
    #                 if total_after_scan > available_stock:
    #                     raise ValidationError(
    #                         f"Qty exceeds available stock for lot {lot.name}. ")
    #
    #                 if existing_line:
    #                     existing_line.product_uom_qty = total_after_scan
    #                     existing_line.price_unit = lot.cost_price
    #                 else:
    #                     new_line = (0, 0, {
    #                         'product_id': lot.product_id.id,
    #                         'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                         'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
    #                         'class_id': lot.product_id.categ_id.parent_id.id,
    #                         'brick_id': lot.product_id.categ_id.id,
    #                         'product_uom_qty': requested_qty,
    #                         'lot_ids': [(4, lot.id)],
    #                         'branded_barcode': lot.ref,
    #                         'type_product': lot.type_product,
    #                         'price_unit': lot.cost_price,
    #                         'sale_serial_type': sale_serial_type
    #                     })
    #                     self.order_line = [new_line] + existing_order_line_cmds
    #                 lot.is_uploaded = True
    #         elif re.match(gs1_pattern, barcode) and self.transfer_type == 'stock_mismatch':
    #             product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
    #
    #             last_scanned = self.env['last.scanned.serial.number'].search([
    #                 ('stock_serial', '=', scanned_number),
    #                 ('type_product', '=', 'un_brand'),
    #             ], limit=1)
    #
    #             if not last_scanned:
    #                 raise ValidationError(f'No lot/serial number found for {scanned_number}.')
    #             available_qty = last_scanned.stock_qty
    #             #  GLOBAL VALIDATION
    #             used_count = self.env['sale.mismatch.stock'].search_count([
    #                 ('serial_number', '=', scanned_number),
    #                 ('sale_order_id.state', '!=', 'cancel'),
    #             ])
    #             current_count = len(self.mismatch_stock_ids.filtered(lambda l: l.serial_number == scanned_number))
    #
    #             if (used_count + current_count) >= available_qty:
    #                 raise ValidationError(
    #                     f"Serial {scanned_number} already used maximum allowed ({available_qty})."
    #                 )
    #             # ---------------- ADD MISMATCH LINE ----------------
    #             self.mismatch_stock_ids = [(0, 0, {
    #                 'serial_number': scanned_number,
    #                 'barcode': barcode,
    #                 'document_name': self.name,
    #                 'stock_qty': available_qty,
    #             })]
    #
    #             # ---------------- UPDATE SINGLE SO LINE ----------------
    #             total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))
    #
    #             existing_line = self.order_line.filtered(
    #                 lambda l: l.product_id.id == product.id
    #             )
    #
    #             if existing_line:
    #                 existing_line.product_uom_qty = total_mismatch_qty
    #             else:
    #                 self.order_line = [(0, 0, {
    #                     'product_id': product.id,
    #                     'product_uom_qty': total_mismatch_qty,
    #                     'price_unit': 1,
    #                 })]
    #
    #         # ----------------------------------------------------------------------------
    #         # EAN13 BARCODE
    #         # ----------------------------------------------------------------------------
    #         elif re.match(ean13_pattern, barcode) and self.transfer_type == 'regular':
    #             ean13_barcode = re.match(ean13_pattern, barcode).group(1)
    #             lots = self.env['stock.quant'].search([
    #                 ('lot_id.ref', '=', ean13_barcode),
    #                 ('quantity', '>', 0),
    #                 ('location_id', '=', location),
    #                 ('lot_id.type_product', '=', 'brand'),
    #                 ('company_id', '=', self.company_id.id)
    #             ])
    #             if not lots:
    #                 raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
    #             product = lots[0].product_id
    #             if product.tracking not in ('serial', 'lot'):
    #                 raise ValidationError("Product must be tracked (serial or lot).")
    #             # ---------------- SERIAL ----------------
    #             if product.tracking == 'serial':
    #                 used_names = set(self.order_line.mapped('lot_ids.name'))
    #                 available_lot = None
    #                 for lot in lots.lot_id:
    #                     sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #                     if lot.name in used_names:
    #                         continue
    #                     existing_orders = global_regular_serial_used_orders(lot.name, sale_serial_type)
    #                     if existing_orders:
    #                         continue
    #                     available_lot = lot
    #                     break
    #                 if not available_lot:
    #                     raise ValidationError("All serials for this product are already used.")
    #
    #                 if available_lot.rs_price <= 0.0:
    #                     raise ValidationError("Some serial numbers are missing landed cost.")
    #
    #                 new_line = (0, 0, {
    #                     'product_id': product.id,
    #                     'family_id': available_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                     'category_id': available_lot.product_id.categ_id.parent_id.parent_id.id,
    #                     'class_id': available_lot.product_id.categ_id.parent_id.id,
    #                     'brick_id': available_lot.product_id.categ_id.id,
    #                     'product_uom_qty': 1,
    #                     'lot_ids': [(4, available_lot.id)],
    #                     'branded_barcode': available_lot.ref,
    #                     'type_product': available_lot.type_product,
    #                     'price_unit': available_lot.cost_price,
    #                     'sale_serial_type': sale_serial_type
    #                 })
    #                 available_lot.is_uploaded = True
    #                 self.order_line = [new_line] + existing_order_line_cmds
    #
    #             # ---------------- LOT (MERGING) ----------------
    #             else:
    #                 remaining_qty = self.entered_qty
    #                 if not remaining_qty or remaining_qty <= 0:
    #                     raise ValidationError("Enter a valid quantity.")
    #                 used_names = set(self.order_line.mapped('lot_ids.name'))
    #                 for quant in lots:
    #                     if remaining_qty <= 0:
    #                         break
    #                     lot = quant.lot_id
    #                     sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #                     available_stock = quant.quantity
    #                     global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
    #                     existing_line = get_existing_line(lot, sale_serial_type)
    #                     line_used_qty = sum(existing_line.mapped('product_uom_qty'))
    #                     effective_available = available_stock - global_used_qty - existing_line.product_uom_qty
    #                     if effective_available <= 0:
    #                         continue
    #                     consume = min(remaining_qty, effective_available)
    #                     # Merge or create
    #                     if existing_line:
    #                         existing_line.product_uom_qty = line_used_qty + consume
    #                         existing_line.price_unit = lot.cost_price
    #                     else:
    #                         new_line = (0, 0, {
    #                             'product_id': product.id,
    #                             'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                             'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
    #                             'class_id': lot.product_id.categ_id.parent_id.id,
    #                             'brick_id': lot.product_id.categ_id.id,
    #                             'product_uom_qty': consume,
    #                             'lot_ids': [(4, lot.id)],
    #                             'branded_barcode': lot.ref,
    #                             'type_product': lot.type_product,
    #                             'price_unit': lot.cost_price,
    #                             'sale_serial_type': sale_serial_type
    #                         })
    #                         self.order_line = [new_line] + existing_order_line_cmds
    #                     lot.is_uploaded = True
    #                     remaining_qty -= consume
    #                 if remaining_qty > 0:
    #                     raise ValidationError(
    #                         f"Only {self.entered_qty - remaining_qty} qty available. "
    #                         f"Missing {remaining_qty} qty."
    #                     )
    #         elif re.match(ean13_pattern, barcode) and self.transfer_type == 'damage':
    #             ean13_barcode = re.match(ean13_pattern, barcode).group(1)
    #             lots = self.env['stock.quant'].search([
    #                 ('lot_id.ref', '=', ean13_barcode),
    #                 ('quantity', '>', 0),
    #                 ('location_id', '=', location),
    #                 ('lot_id.type_product', '=', 'brand'),
    #                 ('company_id', '=', self.company_id.id)
    #             ])
    #             if not lots:
    #                 raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
    #             product = lots[0].product_id
    #             if product.tracking not in ('serial', 'lot'):
    #                 raise ValidationError("Product must be tracked (serial or lot).")
    #             # ---------------- SERIAL ----------------
    #             if product.tracking == 'serial':
    #                 used_names = set(self.order_line.mapped('lot_ids.name'))
    #                 available_lot = None
    #                 for lot in lots.lot_id:
    #                     sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #                     if lot.name in used_names:
    #                         continue
    #                     existing_orders = global_damage_serial_used_orders(lot.name, sale_serial_type)
    #                     if existing_orders:
    #                         continue
    #                     available_lot = lot
    #                     break
    #                 if not available_lot:
    #                     raise ValidationError("All serials for this product are already used.")
    #
    #                 if available_lot.rs_price <= 0.0:
    #                     raise ValidationError("Some serial numbers are missing landed cost.")
    #
    #                 new_line = (0, 0, {
    #                     'product_id': product.id,
    #                     'family_id': available_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                     'category_id': available_lot.product_id.categ_id.parent_id.parent_id.id,
    #                     'class_id': available_lot.product_id.categ_id.parent_id.id,
    #                     'brick_id': available_lot.product_id.categ_id.id,
    #                     'product_uom_qty': 1,
    #                     'lot_ids': [(4, available_lot.id)],
    #                     'branded_barcode': available_lot.ref,
    #                     'type_product': available_lot.type_product,
    #                     'price_unit': available_lot.cost_price,
    #                     'sale_serial_type': sale_serial_type
    #                 })
    #                 available_lot.is_uploaded = True
    #                 self.order_line = [new_line] + existing_order_line_cmds
    #
    #             # ---------------- LOT (MERGING) ----------------
    #             else:
    #                 remaining_qty = self.entered_qty
    #                 if not remaining_qty or remaining_qty <= 0:
    #                     raise ValidationError("Enter a valid quantity.")
    #                 used_names = set(self.order_line.mapped('lot_ids.name'))
    #                 for quant in lots:
    #                     if remaining_qty <= 0:
    #                         break
    #                     lot = quant.lot_id
    #                     sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #                     available_stock = quant.quantity
    #                     global_used_qty = global_damage_lot_qty(lot, sale_serial_type)
    #                     existing_line = get_existing_line(lot, sale_serial_type)
    #                     line_used_qty = sum(existing_line.mapped('product_uom_qty'))
    #                     effective_available = available_stock - global_used_qty - existing_line.product_uom_qty
    #                     if effective_available <= 0:
    #                         continue
    #                     consume = min(remaining_qty, effective_available)
    #                     # Merge or create
    #                     if existing_line:
    #                         existing_line.product_uom_qty = line_used_qty + consume
    #                         existing_line.price_unit = lot.cost_price
    #                     else:
    #                         new_line = (0, 0, {
    #                             'product_id': product.id,
    #                             'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                             'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
    #                             'class_id': lot.product_id.categ_id.parent_id.id,
    #                             'brick_id': lot.product_id.categ_id.id,
    #                             'product_uom_qty': consume,
    #                             'lot_ids': [(4, lot.id)],
    #                             'branded_barcode': lot.ref,
    #                             'type_product': lot.type_product,
    #                             'price_unit': lot.cost_price,
    #                             'sale_serial_type': sale_serial_type
    #                         })
    #                         self.order_line = [new_line] + existing_order_line_cmds
    #                     lot.is_uploaded = True
    #                     remaining_qty -= consume
    #                 if remaining_qty > 0:
    #                     raise ValidationError(
    #                         f"Only {self.entered_qty - remaining_qty} qty available. "
    #                         f"Missing {remaining_qty} qty."
    #                     )
    #         elif re.match(ean13_pattern, barcode) and self.transfer_type == 'stock_mismatch':
    #             ean13_barcode = re.match(ean13_pattern, barcode).group(1)
    #
    #             last_scanned = self.env['last.scanned.serial.number'].search([
    #                 ('stock_product_barcode', '=', ean13_barcode),
    #                 ('type_product', '=', 'brand'),
    #             ], limit=1)
    #
    #             if not last_scanned:
    #                 raise ValidationError(f'No lot/serial number found for {ean13_barcode}.')
    #             available_qty = last_scanned.stock_qty
    #             # 🔴 GLOBAL VALIDATION
    #             used_count = self.env['sale.mismatch.stock'].search_count([
    #                 ('barcode', '=', ean13_barcode),
    #                 ('sale_order_id.state', '!=', 'cancel'),
    #             ])
    #             current_count = len(self.mismatch_stock_ids.filtered(lambda l: l.barcode == ean13_barcode))
    #
    #             if (used_count + current_count) >= available_qty:
    #                 raise ValidationError(
    #                     f"Serial {ean13_barcode} already used maximum allowed ({available_qty})."
    #                 )
    #             # ---------------- ADD MISMATCH LINE ----------------
    #             self.mismatch_stock_ids = [(0, 0, {
    #                 'serial_number': ean13_barcode,
    #                 'barcode': ean13_barcode,
    #                 'document_name': self.name,
    #                 'stock_qty': available_qty,
    #             })]
    #
    #             # ---------------- UPDATE SINGLE SO LINE ----------------
    #             total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))
    #
    #             existing_line = self.order_line.filtered(
    #                 lambda l: l.product_id.id == product.id
    #             )
    #
    #             if existing_line:
    #                 existing_line.product_uom_qty = total_mismatch_qty
    #             else:
    #                 self.order_line = [(0, 0, {
    #                     'product_id': product.id,
    #                     'product_uom_qty': total_mismatch_qty,
    #                     'price_unit': 1,
    #                 })]
    #         # ----------------------------------------------------------------------------
    #         # CUSTOM SERIAL BARCODE
    #         # ----------------------------------------------------------------------------
    #         elif re.match(custom_serial_pattern, barcode) and self.transfer_type != 'stock_mismatch':
    #             prefix = re.match(custom_serial_pattern, barcode).group(1)
    #             Quant = self.env['stock.quant']
    #
    #             # ---------------- UNBRANDED (UNCHANGED) ----------------
    #             lots = Quant.search([
    #                 ('quantity', '>', 0),
    #                 ('company_id', '=', self.company_id.id),
    #                 ('location_id', '=', location),
    #                 ('lot_id.name', '=', prefix),
    #                 ('lot_id.type_product', '=', 'un_brand'),
    #             ])
    #
    #             is_branded = False
    #             if not lots:
    #                 # ---------------- BRANDED ----------------
    #                 lots = Quant.search([
    #                     ('quantity', '>', 0),
    #                     ('company_id', '=', self.company_id.id),
    #                     ('location_id', '=', location),
    #                     ('lot_id.ref', '=', prefix),
    #                     ('lot_id.type_product', '=', 'brand'),
    #                 ])
    #                 is_branded = True
    #
    #             if not lots:
    #                 raise ValidationError(f"No lots found for custom barcode {prefix}")
    #
    #             selected_lot = None
    #             qty = 0
    #
    #             # Used serials in current order
    #             used_serials = set(
    #                 self.order_line.mapped('lot_ids.name')
    #             )
    #
    #             # FIFO: always pick lowest ID first
    #             for lot in lots.lot_id.sorted(key=lambda l: l.id):
    #                 product = lot.product_id
    #                 sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
    #
    #                 # ---------------- SERIAL ----------------
    #                 if product.tracking == 'serial':
    #
    #                     if self.entered_qty and self.entered_qty > 1:
    #                         raise ValidationError("Serial product: Qty must be 1.")
    #
    #                     # 🔴 UNBRANDED → OLD BEHAVIOR (STRICT)
    #                     if not is_branded:
    #                         if lot.name in used_serials:
    #                             raise ValidationError(
    #                                 f"Serial {lot.name} already used in this order."
    #                             )
    #                         existing_orders = global_regular_serial_used_orders(
    #                             lot.name, sale_serial_type
    #                         )
    #                         if existing_orders:
    #                             raise ValidationError(
    #                                 f"Serial {lot.name} already used in: {', '.join(set(existing_orders))}"
    #                             )
    #                         selected_lot = lot
    #                         qty = 1
    #                         break
    #
    #                     # 🟢 BRANDED → NEW FIFO BEHAVIOR
    #                     if lot.name in used_serials:
    #                         continue
    #
    #                     existing_orders = global_regular_serial_used_orders(
    #                         lot.name, sale_serial_type
    #                     )
    #                     if existing_orders:
    #                         continue
    #
    #                     # First free serial found
    #                     selected_lot = lot
    #                     qty = 1
    #                     break
    #
    #                 # ---------------- LOT (UNCHANGED) ----------------
    #                 else:
    #                     if not self.entered_qty or self.entered_qty <= 0:
    #                         raise ValidationError("Enter a valid quantity.")
    #
    #                     requested_qty = self.entered_qty
    #                     available_stock = sum(lots.mapped('quantity'))
    #                     global_used_qty = global_regular_lot_qty(lot, sale_serial_type)
    #                     existing_line = get_existing_line(lot, sale_serial_type)
    #                     line_used_qty = sum(existing_line.mapped('product_uom_qty'))
    #                     total_after_scan = line_used_qty + requested_qty
    #
    #                     if global_used_qty + requested_qty > available_stock:
    #                         raise ValidationError(
    #                             f"Qty exceeds available stock for lot {lot.name}. "
    #                             f"Available: {available_stock - global_used_qty}"
    #                         )
    #
    #                     if total_after_scan + global_used_qty > available_stock:
    #                         raise ValidationError(
    #                             f"Qty exceeds available stock for lot {lot.name}."
    #                         )
    #
    #                     selected_lot = lot
    #                     qty = requested_qty
    #                     break
    #
    #             if not selected_lot:
    #                 raise ValidationError(
    #                     f"No available serial/lot found for barcode {prefix}"
    #                 )
    #
    #             if selected_lot.rs_price <= 0.0:
    #                 raise ValidationError("Some serial numbers are missing landed cost.")
    #
    #             # ---------------- MERGE / CREATE ----------------
    #             existing_line = get_existing_line(selected_lot, sale_serial_type)
    #             if existing_line:
    #                 existing_line.product_uom_qty += qty
    #                 existing_line.price_unit = selected_lot.cost_price
    #             else:
    #                 new_line = (0, 0, {
    #                     'product_id': selected_lot.product_id.id,
    #                     'family_id': selected_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #                     'category_id': selected_lot.product_id.categ_id.parent_id.parent_id.id,
    #                     'class_id': selected_lot.product_id.categ_id.parent_id.id,
    #                     'brick_id': selected_lot.product_id.categ_id.id,
    #                     'product_uom_qty': qty,
    #                     'lot_ids': [(4, selected_lot.id)],
    #                     'branded_barcode': selected_lot.ref,
    #                     'type_product': selected_lot.type_product,
    #                     'price_unit': selected_lot.cost_price,
    #                     'sale_serial_type': sale_serial_type
    #                 })
    #                 self.order_line = [new_line] + existing_order_line_cmds
    #
    #             selected_lot.is_uploaded = True
    #
    #         elif re.match(custom_serial_pattern, barcode) and self.transfer_type == 'stock_mismatch':
    #             match = re.match(custom_serial_pattern, barcode)
    #             prefix = match.group(1)
    #             SerialModel = self.env['last.scanned.serial.number']
    #             # -------------------------------------------------
    #             # 1️⃣ FIND RECORD (Try un_brand first, then brand)
    #             # -------------------------------------------------
    #             last_scanned = SerialModel.search([
    #                 ('stock_serial', '=', prefix),
    #                 ('type_product', '=', 'un_brand'),
    #             ], limit=1)
    #             if not last_scanned:
    #                 last_scanned = SerialModel.search([
    #                     ('stock_serial', '=', prefix),
    #                     ('type_product', '=', 'brand'), ], limit=1)
    #
    #             if not last_scanned:
    #                 raise ValidationError(f'No lot/serial number found for {prefix}.')
    #
    #             available_qty = last_scanned.stock_qty
    #             # -------------------------------------------------
    #             # 2️⃣ GLOBAL DUPLICATE VALIDATION
    #             # -------------------------------------------------
    #             key_field = 'serial_number' if last_scanned.type_product == 'un_brand' else 'barcode'
    #             key_value = prefix if key_field == 'serial_number' else barcode
    #             used_count = self.env['sale.mismatch.stock'].search_count([
    #                 (key_field, '=', key_value),
    #                 ('sale_order_id.state', '!=', 'cancel'),
    #                 ('sale_order_id', '!=', self.id),
    #             ])
    #             if key_field == 'serial_number':
    #                 used_current_count = len(
    #                     self.mismatch_stock_ids.filtered(
    #                         lambda l: l.serial_number == key_value
    #                     )
    #                 )
    #             else:
    #                 used_current_count = len(
    #                     self.mismatch_stock_ids.filtered(
    #                         lambda l: l.barcode == key_value
    #                     )
    #                 )
    #             if (used_count + used_current_count) >= available_qty:
    #                 raise ValidationError(
    #                     f"{key_value} already used maximum allowed ({available_qty})."
    #                 )
    #             # -------------------------------------------------
    #             # 3️⃣ ADD MISMATCH LINE
    #             # -------------------------------------------------
    #             self.mismatch_stock_ids = [(0, 0, {
    #                 'serial_number': prefix,
    #                 'barcode': barcode,
    #                 'document_name': self.name,
    #                 'stock_qty': available_qty,
    #
    #             })]
    #             # -------------------------------------------------
    #             # 4️⃣ UPDATE SINGLE SALE ORDER LINE
    #             # -------------------------------------------------
    #             total_mismatch_qty = sum(self.mismatch_stock_ids.mapped('stock_qty'))
    #             existing_line = self.order_line.filtered(
    #                 lambda l: l.product_id.id == product.id
    #             )
    #             if existing_line:
    #                 existing_line.product_uom_qty = total_mismatch_qty
    #             else:
    #                 self.order_line = [(0, 0, {
    #                     'product_id': product.id,
    #                     'product_uom_qty': total_mismatch_qty,
    #                     'price_unit': 1,
    #                 })]
    #
    #         else:
    #             raise ValidationError('Invalid barcode format.')
    #
    #         self.barcode_scanned = False
    #         self.entered_qty = False

    # def action_confirm(self):
    #     res = super().action_confirm()
    #
    #     for order in self:
    #
    #         # get delivery created from this sale order
    #         pickings = order.picking_ids
    #         for picking in pickings:
    #             picking.transfer_type = 'hired'
    #             for line in order.hired_product_ids:
    #                 line.copy({
    #                     'picking_id': picking.id,
    #                     'sale_order_id': False
    #                 })
    #
    #     return res
    def action_confirm(self):
        for order in self:
            if order.transfer_type == 'hpo':

                hpo_type = self.env['stock.picking.type'].search([
                    ('stock_picking_type', '=', 'hpo')
                ], limit=1)

                hpi_type = self.env['stock.picking.type'].search([
                    ('stock_picking_type', '=', 'hpi')
                ], limit=1)

                if not hpo_type or not hpi_type:
                    raise ValidationError(
                        _("Operation Types HPO and HPI are not configured. Please create them before confirming the Sale Order.")
                    )

        res = super().action_confirm()

        for order in self:
            pickings = order.picking_ids
            for picking in pickings:
                picking.transfer_type = 'hired'
                for line in order.hired_product_ids:
                    line.copy({
                        'picking_id': picking.id,
                        'sale_order_id': False
                    })

        return res

    def action_cancel(self):
        for order in self:
            done_pickings = order.picking_ids.filtered(lambda p: p.state == 'done')

            if done_pickings:
                raise ValidationError(
                    _("You cannot cancel this Sale Order because the delivery has already been validated."))

        return super(SaleOrder, self).action_cancel()

    def write(self, vals):
        res = super().write(vals)

        if 'state' in vals:
            for order in self:
                lots = order.hired_product_ids.mapped('lot_number')

                if not lots:
                    continue

                if order.state == 'cancel':
                    lots.write({'hired_product': False})
                else:
                    lots.write({'hired_product': True})

        return res

    @api.onchange('transfer_type')
    def _onchange_transfer_type(self):

        product = self.env['product.product'].search(
            [('name', '=', 'Hired Product')],
            limit=1
        )

        # Auto create product if not exists
        if not product and self.transfer_type == 'hpo':
            product = self.env['product.product'].create({
                'name': 'Hired Product',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 0.0,
            })

        if self.transfer_type == 'hpo' and product:
            existing_line = self.order_line.filtered(lambda l: l.product_id == product)
            if not existing_line:
                self.order_line = [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 0.0,
                    'price_unit': 0.0,
                })]

        else:
            self.order_line = [(5, 0, 0)]
            self.hired_product_ids = [(5, 0, 0)]

    def action_print_hired_products(self):
        return self.env.ref(
            'nhcl_customizations.report_hired_products'
        ).report_action(self)

    @api.model
    def auto_cancel_old_sale_orders(self):
        today = fields.Datetime.now()
        deadline_date = today - timedelta(days=7)

        # Get Bot User (replace login with your bot login)
        bot_user = self.env.ref('base.user_root').id
        if not bot_user:
            return  # or raise error
        SaleOrder = self.env['sale.order'].sudo()
        sale_orders = SaleOrder.search([
            ('state', 'in', ['sale']),
            ('date_order', '<=', deadline_date),
        ])
        for order in sale_orders:
            pickings_to_cancel = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            for picking in pickings_to_cancel:
                for move in picking.move_ids_without_package:
                    move.state = 'draft'
                    picking.with_user(bot_user).action_cancel()
            order.with_user(bot_user).state = 'cancel'

    def action_open_import_wizard(self):
        """Open wizard to import barcodes for this sale order"""
        self.ensure_one()
        return {
            'name': 'Import Barcodes',
            'type': 'ir.actions.act_window',
            'res_model': 'order.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    @api.onchange('partner_id')
    def get_so_type(self):
        if self.partner_id and self.env.company.state_id:
            if self.partner_id.state_id.id == self.env.company.state_id.id:
                self.so_type = 'intra_state'
            else:
                self.so_type = 'inter_state'
        else:
            self.so_type = ''

    # Picking Document Lines Creation
    def get_picking_lines(self):
        # Gather lot_id + sale_serial_type combinations already used in other sale orders
        used_lots = self.env['sale.order.line'].sudo().search([
            ('order_id', '!=', self.id),
            ('lot_ids', '!=', False),
            ('sale_serial_type', '!=', False)
        ])
        used_combinations = set()
        for line in used_lots:
            for lot in line.lot_ids:
                used_combinations.add((lot.name, line.sale_serial_type))
        self.order_line.unlink()
        existing_order = self.env['sale.order'].sudo().search(
            [('picking_document', '=', self.picking_document.id), ('id', '!=', self.id)], limit=1)
        if existing_order:
            raise ValidationError(
                f"This picking document '{self.picking_document.name}' is already used in Sale Order '{existing_order.name}'.")

        picking = self.env['stock.picking'].sudo().search([('name', '=', self.picking_document.name)])

        for line in picking.move_line_ids_without_package:
            if not line.product_id:
                raise ValidationError(f"No Products Found in '{picking.name}'.")

            if not line.lot_id:
                continue
            if not line.lot_id.product_qty > 0:
                continue
            # Skip if this (lot.name + serial_type) is already used elsewhere
            if (line.lot_id.name, line.lot_id.serial_type) in used_combinations:
                continue
            lot_ids = [(6, 0, line.lot_id.ids)]
            barcodes = line.lot_id.mapped('ref')
            barcodes = [barcode for barcode in barcodes if barcode]
            branded_barcode_value = ', '.join(set(barcodes))
            self.order_line.create({
                'order_id': self.id,
                'product_id': line.product_id.id,
                'family_id': line.product_id.categ_id.parent_id.parent_id.parent_id.id,
                'category_id': line.product_id.categ_id.parent_id.parent_id.id,
                'class_id': line.product_id.categ_id.parent_id.id,
                'brick_id': line.product_id.categ_id.id,
                'lot_ids': lot_ids,
                'branded_barcode': branded_barcode_value or line.product_id.barcode,
                'type_product': line.type_product,
                'product_uom_qty': line.quantity,
                'price_unit': line.lot_id.cost_price,
                'sale_serial_type': line.lot_id.serial_type,
            })
            line.lot_id.is_uploaded = True


    # Removing sale order lines
    def reset_product_lines(self):
        self.picking_document = False
        for rec in self.order_line:
            for lot in rec.lot_ids:
                lot.is_uploaded = False
            rec.unlink()

    # @api.onchange('so_type')
    # def _check_operation_type(self):
    #     for order in self:
    #         if order.partner_id:
    #             if order.partner_id.parent_id and order.partner_id.parent_id == order.company_id.partner_id:
    #                 # Branch company: only 'HO operation', 'Intra', 'Others' are allowed
    #                 if order.so_type not in ['advertisement','ho_operation', 'intra_state', 'others']:
    #                     raise ValidationError("Invalid selection for a branch. Only 'Advt.', 'HO Operation', 'Intra', and 'Others' are allowed.")
    #             else:
    #                 # Main company: only 'HO operation', 'Inter', 'Others' are allowed
    #                 if order.so_type not in ['advertisement','ho_operation', 'inter_state', 'others']:
    #                     raise ValidationError("Invalid selection for a main companies. Only 'Advt.', 'HO Operation', 'Inter', and 'Others' are allowed.")

    @api.depends('so_type')
    def _compute_nhcl_so_type(self):
        if self.so_type == 'ho_operation':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'advertisement':
            self.dummy_so_type = 'advertisement'
        elif self.so_type == 'others':
            self.dummy_so_type = 'others'
        elif self.so_type == 'inter_state':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'intra_state':
            self.dummy_so_type = 'ho_operation'
        else:
            self.dummy_so_type = ''

    def inter_company_create_purchase_order(self, company):
        """ Create a Purchase Order from the current SO (self)
            Note : In this method, reading the current SO is done as sudo, and the creation of the derived
            PO as intercompany_user, minimizing the access right required for the trigger user
            :param company : the company of the created PO
            :rtype company : res.company record
        """
        for rec in self:
            if not company or not rec.company_id.partner_id:
                continue

            # find user for creating and validating SO/PO from company
            intercompany_uid = company.intercompany_user_id and company.intercompany_user_id.id or False
            if not intercompany_uid:
                raise ValidationError(_('Provide one user for intercompany relation for %(name)s '), name=company.name)
            # check intercompany user access rights
            if not self.env['purchase.order'].with_user(intercompany_uid).check_access_rights('create',
                                                                                              raise_exception=False):
                raise ValidationError(
                    _("Inter company user of company %s doesn't have enough access rights", company.name))

            company_partner = rec.company_id.partner_id.with_user(intercompany_uid)
            # create the PO and generate its lines from the SO
            # read it as sudo, because inter-compagny user can not have the access right on PO
            po_vals = rec.sudo()._prepare_purchase_order_data(company, company_partner)
            inter_user = self.env['res.users'].sudo().browse(intercompany_uid)
            for line in rec.order_line.sudo():
                po_vals['order_line'] += [(0, 0, rec._prepare_purchase_order_line_data(line, rec.date_order, company))]
            purchase_order = self.env['purchase.order'].create(po_vals)
            for k in purchase_order.order_line:
                k._compute_tax_id()

            msg = _("Automatically generated from %(origin)s of company %(company)s.", origin=self.name,
                    company=company.name)
            purchase_order.message_post(body=msg)

            # write customer reference field on SO
            if not rec.client_order_ref:
                rec.client_order_ref = purchase_order.name

            # auto-validate the purchase order if needed
            if company.auto_validation:
                purchase_order.with_user(intercompany_uid).button_confirm()

    def _prepare_purchase_order_data(self, company, company_partner):
        """ Generate purchase order values, from the SO (self)
            :param company_partner : the partner representing the company of the SO
            :rtype company_partner : res.partner record
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        self.ensure_one()
        # find location and warehouse, pick warehouse from company object
        warehouse = company.warehouse_id and company.warehouse_id.company_id.id == company.id and company.warehouse_id or False
        if not warehouse:
            raise ValidationError(
                _('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies', company.name))
        picking_type_id = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('warehouse_id', '=', warehouse.id)
        ], limit=1)
        if not picking_type_id:
            intercompany_uid = company.intercompany_user_id.id
            picking_type_id = self.env['purchase.order'].with_user(intercompany_uid)._default_picking_type()
        return {
            'name': self.env['ir.sequence'].sudo().next_by_code('purchase.order'),
            'origin': self.name,
            'partner_id': company_partner.id,
            'nhcl_po_type': self.so_type,
            'picking_type_id': picking_type_id.id,
            'date_order': self.date_order,
            'company_id': company.id,
            'fiscal_position_id': company_partner.property_account_position_id.id,
            'payment_term_id': company_partner.property_supplier_payment_term_id.id,
            'auto_generated': True,
            'auto_sale_order_id': self.id,
            'partner_ref': self.name,
            'currency_id': self.currency_id.id,
            'order_line': [],
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_ids = fields.Many2many('stock.lot', string="Serial Numbers")
    branded_barcode = fields.Char(string="Barcode")
    type_product = fields.Selection([('brand', 'Brand'), ('un_brand', 'UnBrand'), ('others', 'Others')],
                                    string='Brand Type', copy=False)
    sale_serial_type = fields.Selection([('regular', 'Regular'), ('return', 'Returned')],
                                        string='Serial Type', copy=False)
    family_id = fields.Many2one('product.category', string='Family', copy=False)
    category_id = fields.Many2one('product.category', string='Category', copy=False)
    class_id = fields.Many2one('product.category', string='Class', copy=False)
    brick_id = fields.Many2one('product.category', string='Brick', copy=False)
    s_no = fields.Integer(string="S.No", compute="_compute_s_no")

    @api.depends('order_id')
    def _compute_s_no(self):
        for rec in self.order_id:
            for index, line in enumerate(rec.order_line, start=1):
                line.s_no = index

    @api.constrains('lot_ids')
    def check_lot_serial_main_location(self):
        location = False
        if self.lot_ids and self.order_id.transfer_type == 'regular':
            location = self.env.ref('stock.stock_location_stock').id
            for i in self:
                lot = self.env['stock.quant'].search(
                    [('lot_id.name', '=', i.lot_ids.name), ('location_id', '=', location), ('quantity', '>', 0)])
                if not lot:
                    raise ValidationError(f"This {i.lot_ids.name} Serial/Lot are not available in the main location")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SaleOrderLine, self).create(vals_list)

        for rec in records:
            for lot in rec.lot_ids:
                if lot.is_under_plan:
                    raise ValidationError(
                        f"This {lot.name} Serial/Lot number is under Audit plan."
                    )

        return records

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.order_id and not self.order_id.so_type:
            # Clear the product_id and raise an error if no stock_type is selected
            self.product_id = False
            raise ValidationError(
                "You must select a SO Type before selecting a product."
            )

    def remove_sale_order_line(self):
        for rec in self:
            # for lot in rec.lot_ids:
            #     lot.is_uploaded = False
            rec.unlink()

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """ Override to ensure lot/serial numbers are carried over to stock moves """
        moves = super(SaleOrderLine, self)._action_launch_stock_rule(previous_product_uom_qty)
        for rec in self:
            for move_id in rec.move_ids:
                move_id.write({
                    'lot_ids': rec.lot_ids.ids
                })
                for move_line in move_id.move_line_ids:
                    if rec.product_id.id == move_line.product_id.id and rec.lot_ids.name == move_line.lot_name:
                        move_line.write({
                            'internal_ref_lot': rec.branded_barcode,

                        })
        for move_line in self.order_id.picking_ids.move_line_ids_without_package:
            if move_line.lot_id:
                move_line.write({
                    'internal_ref_lot': move_line.lot_id.ref,
                    'type_product': move_line.lot_id.type_product,
                    'categ_1': move_line.lot_id.category_1,
                    'categ_2': move_line.lot_id.category_2,
                    'categ_3': move_line.lot_id.category_3,
                    'categ_4': move_line.lot_id.category_4,
                    'categ_5': move_line.lot_id.category_5,
                    'categ_6': move_line.lot_id.category_6,
                    'categ_7': move_line.lot_id.category_7,
                    'categ_8': move_line.lot_id.category_8,
                    'descrip_1': move_line.lot_id.description_1,
                    'descrip_2': move_line.lot_id.description_2,
                    'descrip_3': move_line.lot_id.description_3,
                    'descrip_4': move_line.lot_id.description_4,
                    'descrip_5': move_line.lot_id.description_5,
                    'descrip_6': move_line.lot_id.description_6,
                    'descrip_7': move_line.lot_id.description_7,
                    'descrip_8': move_line.lot_id.description_8,
                    'descrip_9': move_line.lot_id.description_9,
                    'cost_price': move_line.lot_id.cost_price,
                    'mr_price': move_line.lot_id.mr_price,
                    'rs_price': move_line.lot_id.rs_price,
                })
        return moves


class SaleMismatchStock(models.Model):
    _name = 'sale.mismatch.stock'
    _description = 'Sale Mismatch Stock'
    _rec_name = 'serial_number'

    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sale Order",
        ondelete='cascade'
    )

    serial_number = fields.Char(string="Serial Number")
    barcode = fields.Char(string="Barcode")
    document_name = fields.Char(string="Document Name")
    stock_qty = fields.Float(string='Qty', copy=False)




class SaleOrderHiredProduct(models.Model):
    _name = 'sale.order.hired.product'
    _description = 'Sale Order Hired Product'

    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    product_id = fields.Many2one('product.product', string="Product")
    picking_id = fields.Many2one('stock.picking', string="Delivery")
    lot_number = fields.Many2one('stock.lot', string="Lot Number")
    barcode = fields.Char(string="Barcode")
    quantity = fields.Float(string="Quantity")
    returned_scan = fields.Boolean(
        string="Scanned",
        default=False
    )

    def _update_so_qty(self, order):
        hired_product = self.env['product.product'].search(
            [('name', '=', 'Hired Product')], limit=1
        )

        total_qty = sum(order.hired_product_ids.mapped('quantity'))

        line = order.order_line.filtered(lambda l: l.product_id == hired_product)

        if line:
            line.product_uom_qty = total_qty
        else:
            order.order_line = [(0, 0, {
                'product_id': hired_product.id,
                'product_uom_qty': total_qty,
                'price_unit': 0.0,
            })]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # ✅ Update lot flag
        for rec in records:
            if rec.lot_number:
                rec.lot_number.hired_product = True

        # ✅ Update SO qty (avoid duplicate calls)
        sale_orders = records.mapped('sale_order_id')
        for so in sale_orders:
            records.filtered(lambda r: r.sale_order_id == so)._update_so_qty(so)

        return records

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            rec._update_so_qty(rec.sale_order_id)

        return res

    def unlink(self):
        orders = self.mapped('sale_order_id')

        lots = self.mapped('lot_number')
        res = super().unlink()

        if lots:
            lots.write({'hired_product': False})

        for order in orders:
            self._update_so_qty(order)

        return res

