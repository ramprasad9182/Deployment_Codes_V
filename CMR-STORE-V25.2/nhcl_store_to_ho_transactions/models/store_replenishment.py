from collections import defaultdict

from odoo import models, fields, api, _
import logging
import io
import base64
import xlsxwriter

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PriceGradeMaster(models.Model):
    _name = 'price.grade.master'
    _description = 'Price Grade Master'

    name = fields.Char(required=True)
    line_ids = fields.One2many(
        'price.grade.master.line',
        'grade_id',
        string="Price Ranges"
    )
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue
            domain = [
                ('id', '!=', rec.id),
                ('name', '=', rec.name.strip())
            ]
            if self.search_count(domain):
                raise ValidationError("Name must be unique.")

    @api.constrains('line_ids')
    def _check_lines_required(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError("At least one line is required.")


class OfferMaster(models.Model):
    _name = 'offer.master'
    _description = 'Offer Master'
    _order = 'name'

    name = fields.Char(required=True)
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.onchange('name')
    def _onchange_name_upper(self):
        for rec in self:
            if rec.name:
                rec.name = rec.name.upper()

    @api.model
    def create(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'].strip().upper()
        return super().create(vals)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'].strip().upper()
        return super().write(vals)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue
            name = rec.name.strip().upper()
            if self.search_count([
                ('id', '!=', rec.id),
                ('name', '=', name)
            ]):
                raise ValidationError("Offer name must be unique.")


class PriceGradeMasterLine(models.Model):
    _name = 'price.grade.master.line'
    _description = 'Price Grade Master Line'

    grade_id = fields.Many2one('price.grade.master', required=True, ondelete='cascade')
    price_from = fields.Float(required=True)
    price_to = fields.Float(required=True)
    min_qty = fields.Float()
    max_qty = fields.Float()
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.constrains('price_from', 'price_to')
    def _check_price(self):
        for rec in self:
            if rec.price_from > rec.price_to:
                raise ValidationError("Price From must be <= Price To")

    @api.constrains('min_qty', 'max_qty')
    def _check_qty(self):
        for rec in self:
            if rec.min_qty and rec.max_qty and rec.min_qty > rec.max_qty:
                raise ValidationError("Min Qty must be <= Max Qty")

    @api.constrains('price_from', 'price_to', 'grade_id')
    def _check_overlap(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('grade_id', '=', rec.grade_id.id),
                ('price_from', '<=', rec.price_to),
                ('price_to', '>=', rec.price_from),
            ]
            if self.search_count(domain):
                raise ValidationError("Overlapping price ranges not allowed.")


class ReplenishmentSource(models.Model):
    _name = 'replenishment.source'
    _description = 'Replenishment Source'
    _order = 'name'

    name = fields.Char(required=True)
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.model
    def create(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'].strip().upper()
        return super().create(vals)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals['name'].strip().upper()
        return super().write(vals)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue

            if self.search_count([
                ('id', '!=', rec.id),
                ('name', '=', rec.name.strip().upper())
            ]):
                raise ValidationError("Name must be unique.")


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    repl_type = fields.Selection([('fashion', 'Fashions')], string="Replenish Type")
    replenish_id = fields.Many2one('replenishment.source', string="Replenish Source", copy=False)


class StoreReplenishment(models.Model):
    _name = 'store.replenishment'
    _description = 'Store Replenishment'

    name = fields.Char(string="Reference",required=True,copy=False,readonly=True,default='New')
    store_id = fields.Many2one('res.company', default=lambda self:self.env.company.id)
    repl_type = fields.Selection([('regular', 'Regular'),('fashion', 'Fashions')], default='regular', string="Type")
    product_tmpl_id = fields.Many2one('product.template', string='Product')
    product_tmpl_ids = fields.Many2many('product.template','store_repl_product_rel',string="Products")
    brand_attribute_id = fields.Many2one('product.attribute.value', string='Brand', copy=False)
    age_ids = fields.Many2many('product.attribute.value', string='Age', copy=False)
    line_ids = fields.One2many('store.replenishment.line','repl_id',
        string="Replenishment Lines")
    price_from = fields.Float(compute='_compute_parent_values', store=True)
    price_to = fields.Float(compute='_compute_parent_values', store=True)
    min_qty = fields.Float(string='Min Qty', compute='_compute_parent_values', store=True)
    max_qty = fields.Float(string='Max Qty', compute='_compute_parent_values', store=True)
    onhand_qty = fields.Float(string='On Hand Qty', compute='_compute_parent_values', store=True)
    differ_qty = fields.Float(string='Differ Qty', compute='_compute_parent_values', store=True)
    indent_qty = fields.Float(string='Indent Qty', compute='_compute_parent_values', store=True)
    grade_id = fields.Many2one('price.grade.master', string='Grade', copy=False)
    replenish_id = fields.Many2one('replenishment.source', string="Replenish Source", copy=False)
    effective_date = fields.Date(string='Effective Date', copy=False)

    # @api.onchange('repl_type')
    # @api.constrains('repl_type')
    # def _onchange_load_products(self):
    #     if self.repl_type == 'fashion':
    #         templates = self.env['product.template'].search([('repl_type', '=', 'fashion')])
    #         self.product_tmpl_ids = [(6, 0, templates.ids)]


    def open_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Open MBQ',
            'res_model': 'store.replenishment',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_store_to_ho_transactions.view_store_replenishment_form').id,
            'res_id': self.id,
            'target': 'current',
        }

    @api.depends(
        'line_ids.price_from',
        'line_ids.price_to',
        'line_ids.min_qty',
        'line_ids.max_qty',
        'line_ids.onhand_qty',
        'line_ids.differ_qty',
        'line_ids.indent_qty'
    )
    def _compute_parent_values(self):
        for rec in self:
            lines = rec.line_ids
            rec.update({
                'price_from': sum(lines.mapped('price_from')) if lines else 0,
                'price_to': sum(lines.mapped('price_to')) if lines else 0,
                'min_qty': sum(lines.mapped('min_qty')),
                'max_qty': sum(lines.mapped('max_qty')),
                'onhand_qty': sum(lines.mapped('onhand_qty')),
                'differ_qty': sum(lines.mapped('differ_qty')),
                'indent_qty': sum(lines.mapped('indent_qty')),
            })


class StoreReplenishmentLine(models.Model):
    _name = 'store.replenishment.line'
    _description = 'Store Replenishment Line'

    repl_id = fields.Many2one('store.replenishment',required=True,ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', related='repl_id.product_tmpl_id', store=True)
    repl_type = fields.Selection(related='repl_id.repl_type', store=True, string="Type")
    division = fields.Many2one('product.category' ,string="Division", compute='_compute_division', store=True)
    price_from = fields.Float(required=True)
    price_to = fields.Float(required=True)
    min_qty = fields.Float()
    max_qty = fields.Float()
    onhand_qty = fields.Float(compute='_compute_onhand')
    differ_qty = fields.Float(compute='_compute_differ')
    indent_qty = fields.Float(compute='compute_indent_qty')
    price_range = fields.Char(string="Price Range", compute="_compute_price_range", store=True)
    offer_id = fields.Many2one('offer.master', string="Offer")

    @api.depends('price_from', 'price_to')
    def _compute_price_range(self):
        for rec in self:
            if rec.price_from or rec.price_to:
                rec.price_range = f"{int(rec.price_from)}-{int(rec.price_to)}"
            else:
                rec.price_range = False
    

    @api.depends('product_tmpl_id', 'repl_id.repl_type', 'repl_id.product_tmpl_ids')
    def _compute_division(self):
        for rec in self:
            tmpl = rec.repl_id.product_tmpl_ids[:1] if rec.repl_id.product_tmpl_ids else False
            categ = tmpl.categ_id if tmpl else False
            while categ and categ.parent_id:
                categ = categ.parent_id
            rec.division = categ.id if categ else False

    @api.depends(
        'product_tmpl_id',
        'repl_id.repl_type',
        'repl_id.product_tmpl_ids',
        'price_from',
        'price_to'
    )
    def _compute_onhand(self):
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        for rec in self:
            rec.onhand_qty = 0
            company = rec.repl_id.store_id
            if not company:
                continue
            template_ids = rec.repl_id.product_tmpl_ids.ids
            if not template_ids:
                continue

            locations = Location.search([
                ('company_id', '=', company.id),
                ('usage', '=', 'internal')
            ])
            domain = [
                ('location_id', 'in', locations.ids),
                ('lot_id.rs_price', '>=', rec.price_from),
                ('lot_id.rs_price', '<=', rec.price_to),
            ]
            # Apply template filter only when brand and age are NOT selected
            if not rec.repl_id.brand_attribute_id and not rec.repl_id.age_ids:
                domain.append((
                    'product_id.product_tmpl_id',
                    'in',
                    template_ids
                ))
            quants = Quant.sudo().search(domain)
            # Brand filter
            if rec.repl_id.brand_attribute_id:
                brand_id = rec.repl_id.brand_attribute_id.id
                quants = quants.filtered(
                    lambda q:
                    brand_id in
                    q.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids
                )
            # Age filter
            if rec.repl_id.age_ids:
                age_ids = rec.repl_id.age_ids.ids
                quants = quants.filtered(
                    lambda q:
                    bool(
                        set(age_ids) & set(
                            q.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids)
                    )
                )
            rec.onhand_qty = sum(quants.mapped('quantity'))

    @api.depends('product_tmpl_id','max_qty','repl_id.product_tmpl_ids')
    def compute_indent_qty(self):
        POLine = self.env['purchase.order.line']
        Lot = self.env['stock.lot'].sudo()
        for rec in self:
            rec.indent_qty = 0
            company = rec.repl_id.store_id
            if not company:
                continue
            template_ids = rec.repl_id.product_tmpl_ids.ids
            if (
                    not template_ids and
                    not rec.repl_id.brand_attribute_id and
                    not rec.repl_id.age_ids
            ):
                continue
            if not rec.price_range or '-' not in rec.price_range:
                continue
            try:
                price_range = rec.price_range.replace(' ', '')
                min_price, max_price = map(float, price_range.split('-'))
            except Exception:
                continue
            po_domain = [
                ('mbq_plan', '=', rec.price_range),
                ('company_id', '=', company.id),
                ('company_id.nhcl_company_bool', '=', False),
                ('order_id.upload_type', '=', 'normal')
            ]
            lot_domain = [
                ('rs_price', '>=', min_price),
                ('rs_price', '<=', max_price),
                ('company_id', '=', company.id),
                ('company_id.nhcl_company_bool', '=', False),
                ('nhcl_purchase_indent_reference', '!=', False)
            ]
            # Apply template filter only when brand & age not selected
            if (not rec.repl_id.brand_attribute_id and not rec.repl_id.age_ids):
                po_domain.append(('product_template_id', 'in', template_ids))
                lot_domain.append(('product_id.product_tmpl_id', 'in', template_ids))
            po_lines = POLine.search(po_domain)
            lots = Lot.search(lot_domain)
            # ? Brand filter
            if rec.repl_id.brand_attribute_id:
                brand_id = rec.repl_id.brand_attribute_id.id
                po_lines = po_lines.filtered(lambda l: brand_id in
                                                       l.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids)
                lots = lots.filtered(lambda l: brand_id in
                                               l.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids)
            # ? Age filter
            if rec.repl_id.age_ids:
                age_ids = rec.repl_id.age_ids.ids
                po_lines = po_lines.filtered(
                    lambda l:
                    bool(
                        set(age_ids) &
                        set(
                            l.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids
                        )
                    )
                )
                lots = lots.filtered(lambda l:
                                     bool(
                                         set(age_ids) &
                                         set(
                                             l.product_id.product_template_attribute_value_ids.product_attribute_value_id.ids
                                         )
                                     )
                                     )
            total_po_qty = sum(po_lines.mapped('product_qty'))
            total_lot_qty = sum(lots.mapped('product_qty'))
            rec.indent_qty = total_po_qty - total_lot_qty

    @api.depends('onhand_qty', 'max_qty','indent_qty')
    def _compute_differ(self):
        for rec in self:
            rec.differ_qty = rec.max_qty - (rec.onhand_qty + rec.indent_qty)


    def action_export_mbq_excel(self):
        lines = self.env['store.replenishment.line'].search([])
        division_map = {}
        for line in lines:
            div = line.division.name or 'Undefined'
            if div not in division_map:
                division_map[div] = {
                    'onhand_qty': 0.0,
                    'differ_qty': 0.0,
                    'indent_qty': 0.0,
                }
            division_map[div]['onhand_qty'] += line.onhand_qty
            division_map[div]['differ_qty'] += line.differ_qty
            division_map[div]['indent_qty'] += line.indent_qty
        # ---------- CREATE EXCEL ----------
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('MBQ Division')
        sheet.write(0, 0, 'Division')
        sheet.write(0, 1, 'Onhand Qty')
        sheet.write(0, 2, 'Differ Qty')
        sheet.write(0, 3, 'Indent Qty')
        row = 1
        for div, vals in division_map.items():
            sheet.write(row, 0, div)
            sheet.write(row, 1, vals['onhand_qty'])
            sheet.write(row, 2, vals['differ_qty'])
            sheet.write(row, 3, vals['indent_qty'])
            row += 1
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        wizard = self.env['mbq.excel.download'].create({
            'file_name': 'MBQ_Division.xlsx',
            'file_data': file_data
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mbq.excel.download',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new'
        }


class MbqDivisionWizard(models.TransientModel):
    _name = 'mbq.division.wizard'
    _description = 'MBQ Division Wizard'

    file_data = fields.Binary()
    file_name = fields.Char()
    line_ids = fields.One2many('mbq.division.wizard.line','wizard_id')

    def action_generate(self):

        self.line_ids.unlink()

        Quant = self.env['stock.quant']
        POL = self.env['purchase.order.line']
        Lot = self.env['stock.lot']
        Location = self.env['stock.location']

        company = self.env.company
        repl_lines = self.env['store.replenishment.line'].search([])
        division_map = {}
        def get_root_division(categ):
            while categ.parent_id:
                categ = categ.parent_id
            return categ
        for line in repl_lines:
            for product in line.repl_id.product_tmpl_ids:
                division = get_root_division(product.categ_id)
                vals = division_map.setdefault(division.id, {
                    'division': division.name,
                    'products': set(),
                    'max_qty': 0.0
                })
                vals['products'].add(product.id)
                vals['max_qty'] += line.max_qty
        # STORE LOCATIONS
        locations = Location.search([
            ('company_id', '=', company.id),
            ('usage', '=', 'internal')
        ])
        vals = []
        for div_id, data in division_map.items():
            product_ids = list(data['products'])
            # ---------- ONHAND ----------
            quants = Quant.search([
                ('product_id.product_tmpl_id', 'in', product_ids),
                ('location_id', 'in', locations.ids)
            ])
            onhand_qty = sum(quants.mapped('quantity'))
            # ---------- PO ----------
            po_lines = POL.search([
                ('product_id.product_tmpl_id', 'in', product_ids),
                ('order_id.state', '!=', 'cancel'),
                ('order_id.upload_type', '=', 'normal')
            ])
            po_qty = sum(po_lines.mapped('product_uom_qty'))
            po_names = po_lines.mapped('order_id.name')
            # ---------- LOT ----------
            lots = Lot.search([
                ('nhcl_purchase_indent_reference', 'in', po_names),
                ('product_id.product_tmpl_id', 'in', product_ids)
            ])
            lot_qty = sum(lots.mapped('product_qty'))
            indent_qty = po_qty - lot_qty
            differ_qty = data ['max_qty'] - (onhand_qty + indent_qty)
            vals.append((0, 0, {
                'division': data['division'],
                'onhand_qty': onhand_qty,
                'indent_qty': indent_qty,
                'differ_qty': differ_qty,
                'mbq_qty': data ['max_qty'],
            }))

        self.line_ids = vals


    def action_reset(self):
        self.line_ids.unlink()

    def action_export_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('MBQ')
        sheet.write(0, 0, 'Division')
        sheet.write(0, 1, 'Onhand')
        sheet.write(0, 2, 'Differ')
        sheet.write(0, 3, 'Indent')
        row = 1
        for line in self.line_ids:
            sheet.write(row, 0, line.division)
            sheet.write(row, 1, line.onhand_qty)
            sheet.write(row, 2, line.differ_qty)
            sheet.write(row, 3, line.indent_qty)
            row += 1
        workbook.close()
        output.seek(0)
        self.file_data = base64.b64encode(output.read())
        self.file_name = 'MBQ.xlsx'
        return {
            'type': 'ir.actions.act_url',
            'url': (
                       '/web/content/?model=mbq.division.wizard'
                       '&id=%s'
                       '&field=file_data'
                       '&filename_field=file_name'
                       '&download=true'
                   ) % self.id,
            'target': 'self',
        }


class MbqDivisionWizardLine(models.TransientModel):
    _name = 'mbq.division.wizard.line'
    _description = 'MBQ Division Wizard Line'

    wizard_id = fields.Many2one('mbq.division.wizard')
    division = fields.Char(string="Division")
    onhand_qty = fields.Float(string="OnHand Qty")
    differ_qty = fields.Float(string="Differ Qty")
    indent_qty = fields.Float(string="Indent Qty")
    mbq_qty = fields.Float(string="MBQ Qty")


class ReplenishmentWizard(models.TransientModel):
    _name = 'replenishment.wizard'
    _description = 'Replenishment Wizard'

    product_tmpl_id = fields.Many2one('product.template')
    purchase_line_id = fields.Many2one('purchase.order.line')
    line_ids = fields.One2many('replenishment.wizard.line', 'wizard_id')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        product_tmpl_id = self.env.context.get('default_product_tmpl_id')
        if not product_tmpl_id:
            return res
        ReplLine = self.env['store.replenishment.line'].sudo()
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        # -----------------------------
        # FETCH REPLENISHMENT LINES
        # -----------------------------
        Repl = self.env['store.replenishment'].sudo()
        latest_repl = Repl.search([
            ('product_tmpl_ids', 'in', [product_tmpl_id]),
        ], order='effective_date desc, id desc', limit=1)
        if latest_repl:
            domain = [
                ('product_tmpl_ids', 'in', [product_tmpl_id]),
                ('store_id.nhcl_company_bool', '=', False),
            ]
            # Brand filter
            if latest_repl.brand_attribute_id:
                domain.append(('brand_attribute_id', '=', latest_repl.brand_attribute_id.id))
            # Age filter
            if latest_repl.age_ids:
                domain.append(('age_ids', 'in', latest_repl.age_ids.ids))
            latest_repl = Repl.search(domain, order='effective_date desc, id desc', limit=1)
        if not latest_repl:
            return res
        # -----------------------------
        # STEP 2: Get all lines
        # -----------------------------
        lines = latest_repl.line_ids
        if not lines:
            return res
        price_ranges = list(set((l.price_from, l.price_to) for l in lines))
        # -----------------------------
        # LOCATIONS (CURRENT COMPANY ONLY)
        # -----------------------------
        locations = Location.search([
            ('company_id', '=', self.env.company.id),
            ('usage', '=', 'internal')
        ])
        # -----------------------------
        # FETCH QUANTS (ONLY ONCE)
        # -----------------------------
        quants = Quant.search([
            ('location_id', 'in', locations.ids),
            ('product_id.product_tmpl_id', '=', product_tmpl_id),
        ])
        # -----------------------------
        # STOCK MAP (BY PRICE RANGE)
        # -----------------------------
        stock_map = defaultdict(float)
        for q in quants:
            price = q.lot_id.rs_price or 0
            for (pf, pt) in price_ranges:
                if pf <= price <= pt:
                    stock_map[(pf, pt)] += q.quantity
        # -----------------------------
        # GROUP REPLENISHMENT DATA
        # -----------------------------
        grouped = {}
        for line in lines:
            if line.offer_id:
                key = (line.price_from, line.price_to, line.offer_id.id)
            else:
                key = (line.price_from, line.price_to)
            if key not in grouped:
                grouped[key] = {
                    'price_range': line.price_range,
                    'price_from': line.price_from,
                    'price_to': line.price_to,
                    'min_qty': line.min_qty,
                    'max_qty': line.max_qty,
                    'indent_qty': 0,
                    'offer_id': line.offer_id.id,
                }
            grouped[key]['indent_qty'] += line.indent_qty
        # ----------------------------
        # BUILD WIZARD LINES
        # -----------------------------
        wizard_lines = []
        for key, vals in grouped.items():
            onhand_qty = stock_map.get(key, 0)
            differ = vals['max_qty'] - onhand_qty
            to_be = differ - vals['indent_qty']
            wizard_lines.append((0, 0, {
                'price_range': vals['price_range'],
                'price_from': vals['price_from'],
                'price_to': vals['price_to'],
                'min_qty': vals['min_qty'],
                'max_qty': vals['max_qty'],
                'onhand_qty': onhand_qty,
                'differ_qty': differ,
                'indent_qty': vals['indent_qty'],
                'to_be_qty': to_be,
                'offer_id': vals['offer_id'],
            }))
        res['line_ids'] = wizard_lines
        return res

    def action_apply_to_po(self):
        self.ensure_one()
        po_line = self.env['purchase.order.line'].browse(self.env.context.get('default_purchase_line_id'))
        selected_lines = self.line_ids.filtered(lambda l: l.select_line)
        if not selected_lines:
            raise ValidationError("Please select at least one line.")
        if len(selected_lines) > 1:
            raise ValidationError("Please select at only one line.")
        # sort by price
        selected_lines = selected_lines.sorted(key=lambda l: l.price_from)
        # (optional) continuity check
        for i in range(len(selected_lines) - 1):
            if selected_lines[i].price_to + 1 != selected_lines[i + 1].price_from:
                raise ValidationError("Selected ranges must be continuous.")
        mbq_plan_val = selected_lines.price_range
        mbq_plan_max_qty = selected_lines.max_qty
        # ✅ ONLY UPDATE EXISTING LINE
        po_line.write({
            'mbq_plan': mbq_plan_val,
            'mbq_max_qty': mbq_plan_max_qty,
            'offer_id': selected_lines.offer_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_close_wizard(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.select_line)
        if not selected_lines:
            raise ValidationError("At least one line must be selected before closing.")
        return {'type': 'ir.actions.act_window_close'}


class ReplenishmentWizardLine(models.TransientModel):
    _name = 'replenishment.wizard.line'
    _description = 'Replenishment Wizard Line'

    wizard_id = fields.Many2one('replenishment.wizard')
    price_range = fields.Char(string="Price Range")
    price_from = fields.Float(string="Price From")
    price_to = fields.Float(string="Price To")
    min_qty = fields.Float(string="Min Qty")
    max_qty = fields.Float(string="Max Qty")
    onhand_qty = fields.Float(string="Onhand Qty")
    offer_id = fields.Many2one('offer.master', string="Offer")
    differ_qty = fields.Float(string="Differ Qty")
    indent_qty = fields.Float(string="Indent Qty")
    to_be_qty = fields.Float(string="To Be Qty")
    ho_indent_qty = fields.Float(string="HO Indent Qty")
    select_line = fields.Boolean(string="Select")