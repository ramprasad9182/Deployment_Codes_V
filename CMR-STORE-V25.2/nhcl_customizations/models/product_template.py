from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Inherited product.template class to add fields and functions"""
    _inherit = 'product.template'

    nhcl_product_type = fields.Selection([('unbranded', 'Un-Branded'), ('branded', 'Branded'),('others', 'Others')],
                                         string='Brand Type')
    nhcl_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('others', 'Others')],
        string='Article Type', default='ho_operation')
    category_abbr = fields.Char(string='Prefix', store=True, )
    product_suffix = fields.Char(string="Suffix", copy=False, tracking=True)
    max_number = fields.Integer(string='Max')
    serial_no = fields.Char(string="Serial No")
    product_description = fields.Html(string="Product Description")
    web_product = fields.Char(string="Website  Product Name")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
    segment = fields.Selection([('apparel','Apparel'), ('non_apparel','Non Apparel'), ('others','Others')], string="Segment", copy=False, tracking=True)
    item_type = fields.Selection([('inventory', 'Inventory'), ('non_inventory', 'Non Inventory')], string="Item Type", default='inventory',
                                 copy=False, tracking=True)

    @api.depends('categ_id')
    def _compute_category_abbr(self):
        for product in self:
            if product.categ_id:
                product.category_abbr = self._get_category_abbr(product.categ_id.display_name)
            else:
                product.category_abbr = False

    def _get_category_abbr(self, phrase):
        # Split the phrase by '/' and take the first part
        first_segment = phrase.split('/')[0].strip()
        first_segment = first_segment.replace('-', ' ')
        words = first_segment.split()
        if len(words) == 1:
            return words[0][0]
        # Otherwise, get the first letter of each word and combine them
        initials = ''.join(word[0] for word in words if word)
        return initials

    @api.onchange('categ_id')
    def creating_product_name_from_categ(self):
        if self.categ_id and self.nhcl_type == 'ho_operation':
            display_name_modified = self.categ_id.display_name.replace(' / ', '-')
            self.name = display_name_modified


class ProductCategory(models.Model):
    _inherit = 'product.category'

    max_num = fields.Integer(string="Max Number")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            name = vals.get('name')
            parent_id = vals.get('parent_id')

            domain = [('name', '=', name)]
            if parent_id:
                domain.append(('parent_id', '=', parent_id))
            else:
                domain.append(('parent_id', '=', False))

            existing = self.env['product.category'].search(domain, limit=1)

            if existing:
                raise ValidationError(
                    f"Category '{name}' already exists under the same parent."
                )

        return super(ProductCategory, self).create(vals_list)

class ProductProduct(models.Model):
    _inherit = "product.product"

    category_abbr = fields.Char(string='Prefix', store=True)
    product_suffix = fields.Char(string="Suffix", copy=False, tracking=True)
    max_number = fields.Integer(string='Max')
    serial_no = fields.Char(string="Serial No")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
    nhcl_display_name = fields.Char(
        string="NHCL Display Name",
        compute="_compute_nhcl_display_name", store=True)
    nhcl_detailed_type = fields.Selection([
        ('consu', 'Consumable'),
        ('service', 'Service'), ('product', 'Storable')], string='Product Type', compute="_compute_nhcl_detailed_type",
        store=True)
    family_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Division",
                                      store=True)
    class_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Section",
                                     store=True)
    brick_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Department",
                                     store=True)
    category_name_id = fields.Many2one('product.category', string='Brick', related='categ_id', store=True)
    main_loc_qty = fields.Float(compute="_compute_location_wise_qty", store=False)
    damage_loc_qty = fields.Float(compute="_compute_location_wise_qty", store=False)
    return_loc_qty = fields.Float(compute="_compute_location_wise_qty", store=False)
    grc_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="GRC Qty")
    main_damage_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Main-Damage Qty")
    damage_main_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Damage-Main Qty")
    return_main_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Return-Main Qty")
    packets_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Packets Qty")
    goods_return_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Goods Return Qty")
    pos_order_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="POS Qty")
    exchange_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="Exchange Qty")
    hpo_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="HPO Qty")
    hpi_qty = fields.Float(store=False, compute="_compute_operation_type_qty", string="HPI Qty")


    @api.depends('categ_id')
    def _compute_category_levels(self):
        for rec in self:
            parent1 = rec.categ_id.parent_id
            parent2 = parent1.parent_id if parent1 else False
            parent3 = parent2.parent_id if parent2 else False
            rec.brick_categ_id = parent1
            rec.class_categ_id = parent2
            rec.family_categ_id = parent3

    @api.depends_context('warehouse')
    def _compute_operation_type_qty(self):
        if not self:
            return

        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Map your custom types
        type_map = {
            'receipt': 'grc_qty',
            'main_damage': 'main_damage_qty',
            'damage_main': 'damage_main_qty',
            'return_main': 'return_main_qty',
            'return': 'packets_qty',
            'damage': 'goods_return_qty',
            'pos_order': 'pos_order_qty',
            'exchange': 'exchange_qty',
            'hpo': 'hpo_qty',
            'hpi': 'hpi_qty',
        }

        picking_types = PickingType.search([
            ('stock_picking_type', 'in', list(type_map.keys()))
        ])

        pt_to_type = {pt.id: pt.stock_picking_type for pt in picking_types}

        # initialize all fields = 0
        for field in type_map.values():
            self.update({field: 0.0})

        if not picking_types:
            return

        # 🚀 single aggregation
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', picking_types.ids),
            ],
            fields=['product_id', 'product_uom_qty:sum', 'picking_type_id'],
            groupby=['product_id', 'picking_type_id'],
            lazy=False,
        )
        # prepare result
        result = {key: {} for key in type_map.keys()}

        for data in grouped_moves:
            product_id = data['product_id'][0]
            pt_id = data['picking_type_id'][0]
            qty = data['product_uom_qty']

            op_type = pt_to_type.get(pt_id)
            if not op_type:
                continue

            result[op_type][product_id] = result[op_type].get(product_id, 0.0) + qty

        # assign
        for product in self:
            for op_type, field_name in type_map.items():
                value = result[op_type].get(product.id, 0.0)
                product[field_name] = value

    @api.depends_context('warehouse')
    def _compute_location_wise_qty(self):
        if not self:
            return
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        # Fetch locations by type
        locations = Location.search([
            ('cmr_location_type', 'in', ['main_location', 'damage_location', 'return_location'])
        ])
        loc_type_map = {loc.id: loc.cmr_location_type for loc in locations}
        # Initialize
        self.update({
            'main_loc_qty': 0.0,
            'damage_loc_qty': 0.0,
            'return_loc_qty': 0.0,
        })
        if not locations:
            return
        grouped_quants = Quant.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('location_id', 'in', locations.ids),
            ],
            fields=['product_id', 'quantity:sum', 'location_id'],
            groupby=['product_id', 'location_id'],
            lazy=False,
        )
        # Prepare result dict
        result = {
            'main_location': {},
            'damage_location': {},
            'return_location': {},
        }
        for data in grouped_quants:
            product_id = data['product_id'][0]
            loc_id = data['location_id'][0]
            qty = data['quantity']
            loc_type = loc_type_map.get(loc_id)
            if not loc_type:
                continue
            result[loc_type][product_id] = result[loc_type].get(product_id, 0.0) + qty
        for product in self:
            product.main_loc_qty = result['main_location'].get(product.id, 0.0)
            product.damage_loc_qty = result['damage_location'].get(product.id, 0.0)
            product.return_loc_qty = result['return_location'].get(product.id, 0.0)

    @api.depends("name")
    def _compute_nhcl_detailed_type(self):
        for prod in self:
            if prod.detailed_type:
                prod.nhcl_detailed_type = prod.detailed_type
            else:
                prod.nhcl_detailed_type = ''

    @api.depends("name", "product_template_attribute_value_ids")
    def _compute_nhcl_display_name(self):
        for product in self:
            base_name = product.name or ""
            variant_values = product.product_template_attribute_value_ids.sorted(
                key=lambda v: (v.attribute_name or "", v.name or "")
            ).mapped("name")
            if variant_values:
                product.nhcl_display_name = f"{base_name} ({', '.join(variant_values)})"
            else:
                product.nhcl_display_name = base_name

    # @api.depends('name', 'default_code', 'product_tmpl_id')
    # @api.depends_context('display_default_code', 'seller_id', 'company_id', 'partner_id', 'use_partner_name')
    # def _compute_display_name(self):
    #     for rec in self:
    #         super(ProductProduct, self)._compute_display_name()
    #         rec._get_nhcl_display_name()


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.depends("name")
    def _compute_display_name(self):
        super()._compute_display_name()
        for i in self:
            i.display_name = f"{i.name}"


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)


class ProductAging(models.Model):
    _name = 'product.aging'
    _description = "product aging"

    product_aging_ids = fields.One2many('product.aging.line','product_aging_id', string="Product Aging")
    name = fields.Char(string="Prefix Name")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

class ProductAgingLine(models.Model):
    _name = 'product.aging.line'
    _description = "product aging line"

    product_aging_id = fields.Many2one('product.aging', string="Aging")
    name = fields.Char(string="Name")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)



class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    attribute_name = fields.Char(
        related="attribute_line_id.attribute_id.name",
        store=True, translate=True
    )

    _order = "attribute_name"


# class Alias(models.Model):
#     _inherit = 'mail.alias'
#
#     display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

class ProductTag(models.Model):
    _inherit = 'product.tag'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

