import base64
import io
import pandas as pd
from odoo.exceptions import UserError
from odoo import fields, models, _ , api
from datetime import datetime, timedelta, date
from collections import defaultdict
import logging



_logger = logging.getLogger(__name__)


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    stock_lot_ids = fields.Many2many('stock.lot', string="Serial No's", copy=False)

    @api.onchange('stock_lot_ids', 'reward_type')
    def _onchange_stock_lot_ids(self):
        for rec in self:
            if rec.stock_lot_ids:
                products = rec.stock_lot_ids.mapped('product_id')
                if rec.reward_type == 'product':
                    rec.reward_product_ids = [(6, 0, products.ids)]
                    if products and not rec.reward_product_id:
                        rec.reward_product_id = products[0]
                elif rec.reward_type == 'discount_on_product' and hasattr(rec, 'cmr_discount_product_ids'):
                    rec.cmr_discount_product_ids = [(6, 0, products.ids)]
                    if products and not rec.discount_product_id:
                        rec.discount_product_id = products[0]


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    serial_ids = fields.Many2many('stock.lot', string="Serial No's", copy=False)
    category_1_ids = fields.Many2many('product.attribute.value', 'cat_1', string='Color', copy=False,
                                      domain=[('attribute_id.name', '=', 'Color')])
    category_2_ids = fields.Many2many('product.attribute.value', 'cat_2', string='Fit', copy=False,
                                      domain=[('attribute_id.name', '=', 'Fit')])
    category_3_ids = fields.Many2many('product.attribute.value', 'cat_3', string='Brand', copy=False,
                                      domain=[('attribute_id.name', '=', 'Brand')])
    category_4_ids = fields.Many2many('product.attribute.value', 'cat_4', string='Pattern', copy=False,
                                      domain=[('attribute_id.name', '=', 'Pattern')])
    category_5_ids = fields.Many2many('product.attribute.value', 'cat_5', string='Border Type', copy=False,
                                      domain=[('attribute_id.name', '=', 'Border Type')])
    category_6_ids = fields.Many2many('product.attribute.value', 'cat_6', string='Border Size', copy=False,
                                      domain=[('attribute_id.name', '=', 'Border Size')])
    category_7_ids = fields.Many2many('product.attribute.value', 'cat_7', string='Size', copy=False,
                                      domain=[('attribute_id.name', '=', 'Size')])
    category_8_ids = fields.Many2many('product.attribute.value', 'cat_8', string='Design', copy=False,
                                      domain=[('attribute_id.name', '=', 'Design')])
    description_1_ids = fields.Many2many('product.aging.line',string='Product Ageing', copy=False)

    description_2_ids = fields.Many2many('product.attribute.value', 'des_2', string='Range', copy=False,
                                         domain=[('attribute_id.name', '=', 'Range')])
    description_3_ids = fields.Many2many('product.attribute.value', 'des_3', string='Collection', copy=False,
                                         domain=[('attribute_id.name', '=', 'Collection')])
    description_4_ids = fields.Many2many('product.attribute.value', 'des_4', string='Fabric', copy=False,
                                         domain=[('attribute_id.name', '=', 'Fabric')])
    description_5_ids = fields.Many2many('product.attribute.value', 'des_5', string='Exclusive', copy=False,
                                         domain=[('attribute_id.name', '=', 'Exclusive')])
    description_6_ids = fields.Many2many('product.attribute.value', 'des_6', string='Print', copy=False,
                                         domain=[('attribute_id.name', '=', 'Print')])
    description_7_ids = fields.Many2many('product.attribute.value', 'des_7', string='Days Ageing', copy=False)
    description_8_ids = fields.Many2many('product.attribute.value', 'des_8', string='Description 8', copy=False)
    loyalty_line_id = fields.One2many('loyalty.line', 'loyalty_id', string='Loyalty Lines')
    # range_from = fields.Integer(string='Range From', copy=False)
    # range_to = fields.Integer(string='Range To', copy=False)
    ref_product_ids = fields.Many2many('product.product', 'ref_product_id',string="Product", copy=False)
    type_filter = fields.Selection([('filter', 'Attribute Filter'), ('serial', 'Serial'),('cart','Cart'),('grc','GRC')], string='Filter Type', copy=False)
    product_category_ids = fields.Many2many('product.category', string='Categories')
    day_ageing_slab = fields.Selection([('1', '0-30'), ('2', '30-60'),
                                        ('3', '60-90'), ('4', '90-120'),
                                        ('5', '120-150'), ('6', '150-180'),
                                        ('7', '180-210'), ('8', '210-240'),
                                        ('9', '240-270'), ('10', '270-300'),
                                        ('11', '300-330'), ('12', '330-360')
                                        ])
    serial_nos = fields.Text(string="Serials")
    serial_import = fields.Binary(string="Serial Import")
    serial_import_filename = fields.Char(string="File Name")


    def action_import_serials(self):
        Lot = self.env['stock.lot'].sudo()

        for record in self:

            if record.type_filter != 'serial':
                raise UserError(
                    "Please select Filter Type as 'Serial' before uploading."
                )

            if not record.serial_import:
                raise UserError("Please upload a file.")

            record.serial_ids = [(5, 0, 0)]

            try:
                file_data = base64.b64decode(record.serial_import)

                df = pd.read_excel(
                    io.BytesIO(file_data),
                    usecols=[0],
                    dtype=str
                )

            except Exception as e:
                raise UserError(
                    "Could not read Excel file.\n%s" % str(e)
                )

            barcodes = (
                df.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )

            barcodes = [
                x for x in barcodes
                if x and x.lower() not in [
                    'serial',
                    'barcode',
                    'serial no',
                    'serial number'
                ]
            ]

            if not barcodes:
                raise UserError("No barcodes found in file.")

            # duplicates automatic ga remove avuthayi
            barcode_set = set(barcodes)

            # existing barcodes matrame fetch avuthayi
            lots = Lot.search([
                ('ref', 'in', list(barcode_set))
            ])

            # stock unna lots matrame
            stock_lots = lots.filtered(
                lambda l: l.product_qty > 0
            )

            # valid + stock available serials assign
            record.serial_ids = [(6, 0, stock_lots.ids)]

            # record.serial_import = False
            # record.serial_import_filename = False

        return True
    def update_loyalty_serials(self):
        for rec in self:
            matching_lots = self.env['stock.lot']
            product_ids = set()
            # Get matching lots
            if rec.serial_nos:
                serial_list = [
                    s.strip() for s in rec.serial_nos.split(',')
                    if s.strip()
                ]
                matching_lots = self.env['stock.lot'].search([
                    ('name', 'in', serial_list),
                    ('product_qty', '>', 0)
                ])

            # Existing serial numbers
            existing_serials = {
                s.strip() for s in (rec.serial_nos or '').split(',')
                if s.strip()
            }

            loyalty_lines = [(5, 0, 0)]

            # Build loyalty lines and collect products
            for lot in matching_lots:
                existing_serials.add(lot.name)

                if lot.product_id:
                    product_ids.add(lot.product_id.id)

                loyalty_lines.append((0, 0, {
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id,
                }))

            # Write everything at once
            rec.write({
                'serial_ids': [(6, 0, matching_lots.ids)],
                'loyalty_line_id': loyalty_lines,
                'product_ids': [(6, 0, list(product_ids))],
            })
            if rec.program_id:  # Replace promo_id with your actual promotion field
                rec.program_id.reward_ids.write({
                    'discount_product_ids': [(6, 0, list(product_ids))]
                })

        return True

    def apply_loyalty_rule(self):
        for i in self:
            i.loyalty_line_id.unlink()

            distinct_product_ids = set()
            loyalty_line_vals = []
            matching_lots = self.env['stock.lot']

            if i.type_filter in ['serial', 'grc', 'filter']:

                # First preference: Imported serials
                if i.serial_ids:
                    matching_lots = i.serial_ids.filtered(lambda lot: lot.product_qty > 0)

                # Second preference: Manual serial entry
                elif i.serial_nos:
                    serial_list = [s.strip() for s in i.serial_nos.split(',') if s.strip()]

                    matching_lots = self.env['stock.lot'].search([
                        ('name', 'in', serial_list),
                        ('product_qty', '>', 0)
                    ])

                if i.description_8_ids:
                    matching_lots_by_desc = self.env['stock.lot'].search([
                        ('description_8', 'in', i.description_8_ids.ids),
                        ('product_qty', '>', 0),
                        '|',
                            ('location_id', '=', False),
                            ('location_id.usage', '!=', 'customer'),
                    ]).filtered(lambda lot: lot.product_qty > 0)
                    matching_lots |= matching_lots_by_desc

                i.serial_ids = [(6, 0, matching_lots.ids)]

                for lot in matching_lots:
                    if lot.product_id:
                        distinct_product_ids.add(lot.product_id.id)

                    loyalty_line_vals.append((0, 0, {
                        'lot_id': lot.id,
                        'product_id': lot.product_id.id,
                    }))

            i.update({
                'loyalty_line_id': loyalty_line_vals,
                'product_ids': [(6, 0, list(distinct_product_ids))]
            })

        return True

    def reset_to_filters(self):
        self.ensure_one()
        self.loyalty_line_id.unlink()
        self.category_1_ids = False
        self.category_2_ids = False
        self.category_3_ids = False
        self.category_4_ids = False
        self.category_5_ids = False
        self.category_6_ids = False
        self.category_7_ids = False
        self.category_8_ids = False
        self.description_1_ids = False
        self.description_2_ids = False
        self.description_3_ids = False
        self.description_4_ids = False
        self.description_5_ids = False
        self.description_6_ids = False
        self.description_7_ids = False
        self.description_8_ids = False
        self.serial_ids = False
        self.product_ids = False
        self.product_category_id = False
        self.product_tag_id = False
        # self.range_from = False
        # self.range_to = False
        self.ref_product_ids = False
        self.serial_nos = False
        # self.product_ids = False

    # def apply_loyalty_rule(self):
    #     for i in self:
    #         i.loyalty_line_id.unlink()
    #         distinct_product_ids = set()
    #         loyalty_line_vals = []
    #         matching_lots = self.env['stock.lot']
    #         if i.type_filter in ['serial','grc','filter']:
    #             if i.serial_nos:
    #                 serial_list = [s.strip() for s in i.serial_nos.split(',') if s.strip()]
    #                 lots = self.env['stock.lot'].search([('name', 'in', serial_list),('product_qty','>', 0)])
    #                 i.serial_ids = [(6, 0, lots.ids)]
    #                 matching_lots = i.serial_ids
    #                 for lot in matching_lots:
    #                     distinct_product_ids.add(lot.product_id.id)
    #                     loyalty_line_vals.append((0, 0, {
    #                         'lot_id': lot.id,
    #                         'product_id': lot.product_id.id
    #                     }))
    #         i.update({
    #             'loyalty_line_id': loyalty_line_vals,
    #             'product_ids': [(6, 0, list(distinct_product_ids))]
    #         })
    #         return matching_lots

    @api.model_create_multi
    def create(self, vals_list):
        records = super(LoyaltyRule, self).create(vals_list)

        for rec in records:
            if rec.type_filter in ['serial', 'grc', 'filter']:
                rec.apply_loyalty_rule()

        return records

    def write(self, vals):
        if self.env.context.get('skip_loyalty_sync'):
            return super(LoyaltyRule, self).write(vals)

        res = super(LoyaltyRule, self).write(vals)

        if any(rule.type_filter in ['serial', 'grc', 'filter'] for rule in self):
            self.with_context(skip_loyalty_sync=True).apply_loyalty_rule()

        return res


class LoyaltyLine(models.Model):
    _name = 'loyalty.line'
    _description = "loyalty line"

    loyalty_id = fields.Many2one('loyalty.rule',string='Loyalty', copy=False)
    lot_id = fields.Many2one('stock.lot',string='Lot/Serial', copy=False)
    product_id = fields.Many2one('product.product',string='Product', copy=False)
    ref = fields.Char(related="lot_id.ref", string='Barcode', copy=False)


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
    is_active = fields.Boolean(string='Is Active', compute='_compute_is_active', store=True)
    is_vendor_return = fields.Boolean(string='Vendor Return', copy=False)
    promo_type = fields.Selection([('assesment','Assesment'),('in_house','In House')],string='Promo Type',copy=False)

    def update_loyalty_program(self):
        promo = self.env['loyalty.program'].search([('promo_type','=','assesment')])
        for rec in promo:
            for rule in rec.rule_ids:
                rule.update_loyalty_serials()

    @api.depends('date_from', 'date_to')
    def _compute_is_active(self):
        today = date.today()
        for record in self:
            record.is_active = bool(record.date_from and record.date_to and record.date_from <= today <= record.date_to)

    def cron_update_is_active(self):
        """Cron job to recompute 'is_active' daily"""
        records = self.search([])
        records._compute_is_active()

    def cron_apply_in_house_loyalty_rules(self):
        """Cron job to find loyalty programs with promo_type = 'in_house' and call apply_loyalty_rule() on their rules"""
        programs = self.search([('promo_type', '=', 'in_house')])
        rules = programs.rule_ids
        if rules:
            rules.apply_loyalty_rule()
        rewards = programs.reward_ids
        if rewards:
            for record in rewards:
                if record.discount_applicability == 'specific':
                    for (i, j) in zip(range(0, len(record.program_id.rule_ids)),
                                      range(0, len(record.program_id.reward_ids))):
                        record.program_id.reward_ids[j].discount_product_ids = record.program_id.rule_ids[i].product_ids

    @api.model
    def get_total_promo(self):
        # return active promos; leave selection empty by default in UI
        promotions = self.search_read([], ['id', 'name'])
        return {
            'promotions': promotions,  # [{id, name}, ...]
            'promotion_list': []  # empty = no preselected filter
        }

    @api.model
    def search_promotions(self, q="", limit=50):
        domain = [("is_active", "=", True)]
        if q:
            domain.append(("name", "ilike", q))
        recs = self.search(domain, limit=limit, order="name asc")
        return [{"id": r.id, "name": r.name} for r in recs]

    @api.model
    def get_category_summary_from_active_promotions(self, **kwargs):
        """
        kwargs:
          category_ids=[int|dict], promo_ids=[int|dict],
          period_days=int,                           # SOLD window only
          group_by="root"|"parent"|"self" (default "root"),
          company_ids=[int|dict], pos_config_ids=[int|dict]
        Notes:
          - stock.lot.product_qty is treated as the true capacity (total units) for that lot.
          - Each pack_lot reference on a pos.order.line counts as `count = getattr(pack_lot, 'qty', 1)` units.
          - Net sold units for a lot = sum(positive occurrences) - sum(negative occurrences) (clamped to [0, capacity]).
          - Attribution uses chunk-based allocation with LIFO returns; if net allocated units exceed lot capacity, we trim newest allocations.
        """
        from collections import defaultdict
        from datetime import timedelta

        # ---------- helpers
        def _to_ids(val):
            out = []
            for x in (val or []):
                if isinstance(x, int):
                    out.append(x)
                elif isinstance(x, str) and x.isdigit():
                    out.append(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int):
                        out.append(xid)
            return out

        def _grouped_cat(cat, group_by_local):
            if not cat:
                return None
            grp = cat
            if group_by_local == "root":
                while grp.parent_id:
                    grp = grp.parent_id
            elif group_by_local == "parent":
                grp = grp.parent_id or grp
            return grp

        def _iter_rule_categories(rule):
            cats = set()
            if getattr(rule, "product_category_id", False):
                cats.add(rule.product_category_id)
            if hasattr(rule, "product_category_ids"):
                cats.update(rule.product_category_ids)
            if hasattr(rule, "product_tmpl_ids") and rule.product_tmpl_ids:
                cats.update(rule.product_tmpl_ids.mapped("categ_id"))
            if hasattr(rule, "product_ids") and rule.product_ids:
                cats.update(rule.product_ids.mapped("product_tmpl_id.categ_id"))
            return {c for c in cats if c}

        # ---------- parse filters
        filter_cat_ids = set(_to_ids(kwargs.get("category_ids")))
        filter_promo_ids = set(_to_ids(kwargs.get("promo_ids")))
        filter_company_ids = set(_to_ids(kwargs.get("company_ids")))
        filter_config_ids = set(_to_ids(kwargs.get("pos_config_ids")))

        group_by = (kwargs.get("group_by") or "root").lower()

        period_days_raw = kwargs.get("period_days") or 0
        try:
            period_days = int(period_days_raw)
        except Exception:
            period_days = 0

        today = fields.Date.context_today(self)
        since_dt = fields.Datetime.now() - timedelta(days=period_days) if period_days > 0 else None

        # ---------- STRICT active promotion domain (require BOTH dates; today inside window)
        domain_programs = [
            '&', '&', '&',
            ('active', '=', True),
            ('is_active', '=', True),
            '&', ('date_from', '!=', False), ('date_to', '!=', False),
            '&', ('date_from', '<=', today), ('date_to', '>=', today),
        ]
        if filter_promo_ids:
            domain_programs = ['&'] + domain_programs + [('id', 'in', list(filter_promo_ids))]

        promo_model = self.with_context(active_test=True)
        programs = promo_model.search(domain_programs)
        if not programs:
            _logger.info("Dashboard: No ACTIVE promotions with strict domain=%s", domain_programs)
            return []

        # ---------- promo-aware POS attribution (detect field if present)
        line_model = self.env["pos.order.line"]
        _promo_line_field = None
        for f in ("promotion_id", "promo_id", "program_id", "applied_promotion_id", "promotion_applied_id"):
            if f in line_model._fields:
                _promo_line_field = f
                break

        # ---------- per-(promo, grouped category) working map (BUCKETS)
        promo_cat = defaultdict(lambda: {
            "promotion_id": 0,
            "promotion_name": "",
            "category_id": 0,  # grouped category id (per group_by)
            "category_name": "",
            "serial_names": set(),  # whitelist lot names assigned to THIS bucket (no duplication)
            "serial_caps": {},  # lot_name -> capacity (product_qty)
            "cap_total": 0,  # total units for bucket (sum of lot capacities OR numeric caps)
            "sold_serials": 0,  # SOLD UNITS (units consumed), will be set post scan
        })
        promo_serial_pool = defaultdict(set)  # promo_id -> union of whitelist lot names
        promo_serial_capacity = defaultdict(dict)  # promo_id -> {lot_name: capacity}
        promo_targeted_cats = dict()  # promo_id -> set(targeted_category_ids)

        # ---------- build caps & serial pools PER PROMO (bucketized)
        for promo in programs.sudo():
            rules = promo.rule_ids.filtered(lambda r: getattr(r, "active", True))
            if not rules:
                continue

            # self-level targeted categories for this promo (used for "most-specific" mapping)
            targeted_cats_recs = set()
            for rule in rules:
                targeted_cats_recs.update(_iter_rule_categories(rule))
            targeted_cats_recs = {c for c in targeted_cats_recs if c}
            targeted_cats_ids = {c.id for c in targeted_cats_recs}
            promo_targeted_cats[promo.id] = targeted_cats_ids

            # pre-create empty buckets so categories appear even if zero
            for cat in targeted_cats_recs:
                grp = _grouped_cat(cat, group_by)
                if not grp:
                    continue
                if filter_cat_ids and grp.id not in filter_cat_ids:
                    continue
                key = (promo.id, grp.id)
                e = promo_cat[key]
                e["promotion_id"] = promo.id
                e["promotion_name"] = getattr(promo, "name", f"Promotion {promo.id}") or f"Promotion {promo.id}"
                e["category_id"] = grp.id
                e["category_name"] = grp.name or "Uncategorized"

            # now distribute serials/caps into exactly ONE bucket each
            for rule in rules:
                rule_cats = _iter_rule_categories(rule)
                if not rule_cats:
                    continue

                serials = getattr(rule, "serial_ids", self.env["stock.lot"].browse())
                if serials:
                    # SERIAL WHITELIST: map each lot to the most-specific targeted category, then group
                    for lot in serials:
                        lot_name = lot.name or ""
                        if not lot_name:
                            continue
                        try:
                            lot_capacity = int(lot.product_qty or 1)
                        except Exception:
                            lot_capacity = 1
                        prod = getattr(lot, "product_id", False)
                        prod_cat = prod.product_tmpl_id.categ_id if prod else False
                        if not prod_cat:
                            continue
                        # id-based most-specific target
                        node = prod_cat
                        target_self = None
                        while node:
                            if node.id in targeted_cats_ids:
                                target_self = node
                                break
                            node = node.parent_id
                        if not target_self:
                            continue
                        grp = _grouped_cat(target_self, group_by)
                        if not grp or (filter_cat_ids and grp.id not in filter_cat_ids):
                            continue
                        key = (promo.id, grp.id)
                        e = promo_cat[key]
                        e["serial_names"].add(lot_name)  # lot belongs to ONE bucket only
                        e["serial_caps"][lot_name] = lot_capacity
                        promo_serial_pool[promo.id].add(lot_name)
                        promo_serial_capacity[promo.id][lot_name] = lot_capacity
                else:
                    # NUMERIC CAP: only allocate when rule targets exactly ONE category (avoid duplication)
                    cap_numeric = 0
                    for fname in ("qty_cap", "quantity_cap", "qty", "quantity", "limit_qty"):
                        if fname in rule._fields:
                            try:
                                cap_numeric = max(cap_numeric, int(getattr(rule, fname) or 0))
                            except Exception:
                                pass
                    if cap_numeric and len(rule_cats) == 1:
                        only_cat = next(iter(rule_cats))
                        grp = _grouped_cat(only_cat, group_by)
                        if grp and (not filter_cat_ids or grp.id in filter_cat_ids):
                            key = (promo.id, grp.id)
                            e = promo_cat[key]
                            e["cap_total"] += int(cap_numeric)
                    elif cap_numeric and len(rule_cats) > 1:
                        _logger.debug(
                            "Promo %s rule %s numeric cap with multiple categories; skipping cap allocation to avoid double counting.",
                            promo.id, rule.id
                        )

        if not promo_cat:
            _logger.info("Dashboard: No rows after active promo/rule filtering.")
            return []

        # finalize totals per bucket (whitelist size -> sum capacities)
        for (promo_id, cat_id), e in promo_cat.items():
            if e["serial_caps"]:
                # sum capacities for lots in this bucket
                try:
                    e["cap_total"] = sum(int(v or 0) for v in e["serial_caps"].values())
                except Exception:
                    e["cap_total"] = int(e.get("cap_total", 0) or 0)
            else:
                e["cap_total"] = int(e.get("cap_total", 0) or 0)

        # ---------- SOLD scan per promo (net of returns, within scope; period applies ONLY here)
        for promo in programs.sudo():
            domain = [
                ("order_id.state", "in", ["paid", "done"]),
                ("pack_lot_ids.lot_name", "!=", False),
            ]
            if since_dt:
                domain.append(("order_id.date_order", ">=", fields.Datetime.to_string(since_dt)))
            if filter_company_ids:
                domain.append(("order_id.company_id", "in", list(filter_company_ids)))
            if filter_config_ids:
                domain.append(("order_id.config_id", "in", list(filter_config_ids)))

            targeted_cats_ids = promo_targeted_cats.get(promo.id, set()) or set()

            # Prefer explicit promo link; else fall back to the promo's whitelist pool
            if _promo_line_field:
                domain.append((_promo_line_field, "=", promo.id))
                use_fallback_pool = False
                fallback_pool = set()
            else:
                fallback_pool = promo_serial_pool.get(promo.id, set())
                if fallback_pool:
                    domain.append(("pack_lot_ids.lot_name", "in", list(fallback_pool)))
                    use_fallback_pool = True
                else:
                    continue  # cannot attribute sales to this promo

            sold_lines = line_model.sudo().search(domain)
            if not sold_lines:
                # nothing sold for this promo in scope
                continue

            # Net events per serial, with quantities, bucketed by grouped category chosen via most-specific targeted cat
            # events: lot_name -> list[(date, sign, qty, grouped_cat_id)]
            events = defaultdict(list)

            for ln in sold_lines:
                # We count per-pack-lot occurrence quantity; prefer per-pack quantity if available
                sign = 1 if (ln.qty or 0) > 0 else (-1 if (ln.qty or 0) < 0 else 0)
                if not sign:
                    continue
                prod_cat = ln.product_id.product_tmpl_id.categ_id if ln.product_id else False
                # determine target_self by id-based ancestry
                target_self = None
                if prod_cat and targeted_cats_ids:
                    node = prod_cat
                    while node:
                        if node.id in targeted_cats_ids:
                            target_self = node
                            break
                        node = node.parent_id
                grp = _grouped_cat(target_self, group_by) if target_self else None
                grp_id = grp.id if grp else None

                for pl in ln.pack_lot_ids:
                    name = pl.lot_name or ""
                    if not name:
                        continue
                    # fallback pool check
                    if use_fallback_pool and fallback_pool and name not in fallback_pool:
                        continue
                    # count units for this pack lot reference: prefer explicit qty on pl, else 1
                    # (some pos pack lot records store quantity per lot reference; if not, we count the reference as 1)
                    try:
                        count = int(getattr(pl, "qty", 1) or 1)
                    except Exception:
                        count = 1
                    events[name].append((ln.order_id.date_order, sign, count, grp_id))

            # For each lot, compute net sold units and attribute to groups using chunked allocations (LIFO returns)
            for lot_name, evs in events.items():
                # if fallback pool is used, and lot not in pool (shouldn't happen due to earlier check), skip
                if use_fallback_pool and lot_name not in fallback_pool:
                    continue
                # sort by date ascending
                evs.sort(key=lambda t: t[0] or fields.Datetime.now())
                # allocations: list of [qty_allocated, grp_id, date]
                allocations = []
                for (dt, sign, qty, grp_id) in evs:
                    if qty <= 0:
                        continue
                    if sign > 0:
                        # positive sale: allocate chunk to grp_id (grp_id may be None)
                        allocations.append([qty, grp_id, dt])
                    else:
                        # return: remove qty from allocations using LIFO (undo last allocations first)
                        remaining = qty
                        while remaining > 0 and allocations:
                            last = allocations[-1]
                            if last[0] > remaining:
                                last[0] -= remaining
                                remaining = 0
                            else:
                                remaining -= last[0]
                                allocations.pop()
                        # if remaining > 0 here, returns exceeded historical positives; ignore extra returns (net can't go negative)
                # sum allocated units per group
                allocated_total = sum(a[0] for a in allocations)
                # clamp to lot capacity
                lot_capacity = promo_serial_capacity.get(promo.id, {}).get(lot_name, 1)
                if allocated_total > lot_capacity:
                    # If allocations exceed capacity, we trim newest allocations (LIFO trim) until within capacity.
                    # This preserves earliest allocations and discards newest beyond capacity.
                    over = allocated_total - lot_capacity
                    while over > 0 and allocations:
                        last = allocations[-1]
                        if last[0] > over:
                            last[0] -= over
                            over = 0
                        else:
                            over -= last[0]
                            allocations.pop()
                    allocated_total = sum(a[0] for a in allocations)

                # attribute per-group for this lot
                attr_by_group = defaultdict(int)
                for qty_alloc, grp_id, _dt in allocations:
                    if grp_id:
                        attr_by_group[grp_id] += int(qty_alloc)
                    # if grp_id is None, we drop attribution (only grouped buckets count)
                # add capacities & sold units into promo_cat buckets
                # find which grouped bucket(s) this lot belongs to (we earlier assigned lot to EXACT one bucket during building serial_caps)
                # but it's possible allocations went to different grp_ids; we only add sold units to the matched bucket by grp_id
                for grp_id, sold_qty in attr_by_group.items():
                    key = (promo.id, grp_id)
                    if key not in promo_cat:
                        # if bucket was not pre-created (shouldn't happen) create minimal entry
                        e = promo_cat[key]
                        e["promotion_id"] = promo.id
                        e["promotion_name"] = getattr(promo, "name", f"Promotion {promo.id}") or f"Promotion {promo.id}"
                        e["category_id"] = grp_id
                        # try to get category name minimally
                        try:
                            cat_rec = self.env["product.category"].browse(grp_id)
                            e["category_name"] = cat_rec.name or "Uncategorized"
                        except Exception:
                            e["category_name"] = "Uncategorized"
                    # add sold units to this bucket
                    promo_cat[key]["sold_serials"] = int(promo_cat[key].get("sold_serials", 0) or 0) + int(sold_qty)

                # ensure bucket's cap_total includes this lot capacity if not already
                # attempt to find the assigned bucket for this lot from promo_serial_capacity mapping
                # we enumerated promo_cat keys earlier and filled serial_caps, so find the key that contains this lot_name
                assigned_bucket_found = False
                for (p_id, c_id), e in promo_cat.items():
                    if p_id != promo.id:
                        continue
                    if lot_name in e.get("serial_caps", {}):
                        # add capacity to bucket.cap_total if not already accounted (we already summed serial_caps earlier, so this step is redundant
                        # but kept as safety for cases where buckets were created later)
                        try:
                            # already summed earlier; nothing to do
                            assigned_bucket_found = True
                        except Exception:
                            pass
                        break
                # if not found, we will not add capacity (this is an edge case)
                # NOTE: sold counts are only attributed to buckets by grp_id above

            # For buckets that didn't use serials (numeric caps) sold_serials may have been set earlier; nothing else to do here

        # ---------- roll up per grouped category (active promos only)
        final_by_cat = defaultdict(lambda: {
            "category_id": 0,
            "category_name": "",
            "promotion_ids": set(),
            "total_serials": 0,  # now interpreted as TOTAL UNITS
            "sold_serials": 0,  # SOLD UNITS
        })

        for (promo_id, cat_id), e in promo_cat.items():
            if not cat_id:
                continue
            if filter_cat_ids and cat_id not in filter_cat_ids:
                continue
            total = int(e.get("cap_total", 0) or 0)
            sold = int(e.get("sold_serials", 0) or 0)
            row = final_by_cat[cat_id]
            row["category_id"] = cat_id
            row["category_name"] = e.get("category_name") or row.get("category_name") or ""
            if total > 0:
                row["promotion_ids"].add(promo_id)  # counts only promos contributing capacity
            row["total_serials"] += total
            row["sold_serials"] += min(sold, total)

        result = []
        for cat_id, row in final_by_cat.items():
            total = int(row["total_serials"])
            sold = min(int(row["sold_serials"]), total)
            result.append({
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "promotion_count": len(row["promotion_ids"]),
                "promotion_ids": sorted(row["promotion_ids"]),
                "total_serials": total,
                "sold_serials": sold,
                "available_serials": max(0, total - sold),
            })

        result.sort(key=lambda r: (r["category_name"] or "").lower())
        _logger.info("Dashboard: Active promotions=%s (strict domain applied)", programs.ids)
        return result


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def get_parent_product(self):
        rows = self.search_read([('parent_id', '=', False)], ['id', 'name'], order='name asc')
        return {
            'parent_product': rows,  # [{id,name}]
            'parent_list': []  # empty = no preselected filter
        }

    @api.model
    def search_top_categories(self, q="", limit=50):
        domain = [("parent_id", "=", False)]
        if q:
            domain.append(("name", "ilike", q))
        recs = self.search(domain, limit=limit, order="name asc")
        return [{"id": r.id, "name": r.name} for r in recs]
