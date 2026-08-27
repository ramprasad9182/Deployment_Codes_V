import requests

from odoo import fields, models, api, _
from odoo.tools import float_round
from collections import defaultdict

from odoo.exceptions import ValidationError


class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    nhcl_used_card = fields.Boolean(string="Used Card", copy=False)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    gdiscount = fields.Float("Global discount")

    def _convert_to_tax_base_line_dict(self):
        res = super()._convert_to_tax_base_line_dict()
        if self.move_id.pos_order_ids and self.display_type == 'product':
            pos_order = self.move_id.pos_order_ids[0]
            same_prod_inv_lines = self.move_id.invoice_line_ids.filtered(
                lambda l: (not l.display_type or l.display_type == 'product') and l.product_id == self.product_id
            )
            try:
                pos_idx = list(same_prod_inv_lines).index(self)
                same_prod_pos_lines = pos_order.lines.filtered(lambda l: l.product_id == self.product_id)
                if pos_idx < len(same_prod_pos_lines):
                    pos_line = same_prod_pos_lines[pos_idx]
                    quantity = self.quantity or 1.0
                    res['price_unit'] = pos_line.price_subtotal / quantity
                    res['discount'] = 0.0
                    res['handle_price_include'] = False
            except ValueError:
                pass
        return res


class PosOrderLine(models.Model):
    """ The class PosOrder is used to inherit pos.order.line """
    _inherit = 'pos.order.line'

    employe_no = fields.Char(string="Sale Person")
    badge_id = fields.Char(string="Employee Id")
    employ_id = fields.Many2one("hr.employee", string='Employee Name')
    gdiscount = fields.Float("Global discount")
    disc_lines = fields.Char(string="Disc Lines")
    vendor_return_disc_price = fields.Float('Vendor Return Price', copy=False)
    discount_reward = fields.Integer('Discount', copy=False)
    nhcl_cost_price = fields.Float(string="Cost Price", copy=False)
    nhcl_rs_price = fields.Float(string="RS Price", copy=False)
    nhcl_mr_price = fields.Float(string="RS Price", copy=False)

    # PRANAV START
    config_id = fields.Many2one('pos.config', related='order_id.config_id', string="Point of Sale", store=True)
    partner_id = fields.Many2one('res.partner', related='order_id.partner_id', string="Customer", store=True)
    phone = fields.Char(related='partner_id.phone', string="Phone", store=True)
    state = fields.Selection(related='order_id.state', string="Status", store=True)
    total_discount = fields.Float(compute="_compute_total_discount", string="Manual Discount", store=True)
    total_reward_discount = fields.Float(compute="_compute_total_discount", string="R.Discount(A)", store=True)
    nhcl_reward_id = fields.Many2one("loyalty.reward", string="Promo",
                                     compute="_compute_nhcl_reward_id", store=True)
    promo_discount_percentage = fields.Float(string='Promo Discount (%)', compute="_compute_promo_discount", store=True,
                                             help="Report purpose only")
    promo_discount_amount = fields.Float(string='Promo Discount Amount', compute="_compute_promo_discount", store=True,
                                         help="Report purpose only")
    applied_program_id = fields.Many2one('loyalty.program', string='Applied Program', compute="_compute_promo_discount",
                                         store=True, help="Report purpose only")

    # STOP

    @api.depends('discount_reward', 'reward_id')
    def _compute_nhcl_reward_id(self):
        for line in self:
            line.nhcl_reward_id = line.discount_reward or (line.reward_id.id if line.reward_id else False)

    @api.depends('gdiscount', 'discount', 'is_fix_discount_line', 'nhcl_reward_id', 'discount_reward', 'is_reward_line',
                 'reward_id', 'price_unit', 'qty', 'nhcl_rs_price', 'price_subtotal_incl', 'fix_discount_amount')
    def _compute_total_discount(self):
        for line in self:
            if getattr(line, 'is_fix_discount_line', False):
                line.total_discount = 0.00
                line.total_reward_discount = 0.00
                continue
            net_amount = (line.price_unit or 0.0) * (line.qty or 0.0)
            if not net_amount and line.nhcl_rs_price:
                net_amount = (line.qty or 0.0) * (line.nhcl_rs_price or 0.0)

            fix_discount = getattr(line, 'fix_discount_amount', 0.0) or 0.0
            has_reward = bool(line.nhcl_reward_id or line.discount_reward or line.is_reward_line or line.reward_id)
            if has_reward:
                if line.nhcl_reward_id and line.nhcl_reward_id.buy_with_reward_price == 'yes':
                    line.total_reward_discount = 0.00
                    line.total_discount = (net_amount * ((line.gdiscount or 0.0) / 100.0)) + fix_discount
                else:
                    if line.discount or line.gdiscount:
                        reward_discount = net_amount * ((line.discount or 0.0) / 100.0)
                        remaining_amount = net_amount - reward_discount
                        global_discount = remaining_amount * ((line.gdiscount or 0.0) / 100.0)
                        line.total_reward_discount = reward_discount
                        line.total_discount = global_discount + fix_discount
                    else:
                        total_discount_diff = ((line.qty or 0.0) * (line.nhcl_rs_price or line.price_unit or 0.0)) - (
                                    line.price_subtotal_incl or 0.0)
                        reward_discount = total_discount_diff - fix_discount
                        line.total_reward_discount = max(0.0, reward_discount)
                        line.total_discount = fix_discount
            else:
                if line.discount or line.gdiscount:
                    reward_discount = net_amount * ((line.discount or 0.0) / 100.0)
                    remaining_amount = net_amount - reward_discount
                    global_discount = remaining_amount * ((line.gdiscount or 0.0) / 100.0)
                    line.total_reward_discount = 0.00
                    line.total_discount = reward_discount + global_discount + fix_discount
                else:
                    total_discount_diff = ((line.qty or 0.0) * (line.nhcl_rs_price or line.price_unit or 0.0)) - (
                                line.price_subtotal_incl or 0.0)
                    line.total_reward_discount = 0.00
                    line.total_discount = max(0.0, total_discount_diff)

    @api.depends('order_id.lines', 'order_id.lines.reward_id', 'order_id.lines.price_subtotal_incl',
                 'order_id.lines.reward_identifier_code', 'order_id.lines.total_reward_discount')
    def _compute_promo_discount(self):
        orders = self.mapped('order_id')
        line_vals = {}

        for order in orders:
            if not order:
                continue

            # Find all reward/discount lines (excluding fixed discount lines)
            reward_lines = order.lines.filtered(
                lambda l: getattr(l, 'is_reward_line', False) and not getattr(l, 'is_fix_discount_line', False)
            )

            # Find all target/cart lines (excluding reward lines, fixed discount lines, and lines where total_reward_discount/promo is set)
            cart_lines = order.lines.filtered(
                lambda l: not getattr(l, 'is_fix_discount_line', False) and not getattr(l, 'is_reward_line',
                                                                                        False) and not l.total_reward_discount and not (
                        getattr(l, 'reward_id', False) or
                        getattr(l, 'discount_reward', False) or
                        getattr(l, 'nhcl_reward_id', False)
                )
            )

            # Initialize default values for every line in the order
            for l in order.lines:
                r_id = l.reward_id or l.nhcl_reward_id or l.discount_reward
                if r_id and not getattr(l, 'is_reward_line', False):
                    line_vals[l.id] = {
                        'percentage': l.discount,
                        'program_id': r_id.program_id.id
                    }
                else:
                    line_vals[l.id] = {
                        'percentage': 0.0,
                        'program_id': False
                    }

            for rl in reward_lines:
                reward = getattr(rl, 'reward_id', self.env['loyalty.reward'])
                if not reward:
                    reward = getattr(rl, 'nhcl_reward_id', self.env['loyalty.reward'])

                if not reward or reward.reward_type not in ('discount', 'discount_on_product'):
                    continue

                program = reward.program_id
                if not program:
                    continue

                # Absolute discount amount of this reward line
                discount_amount = abs(rl.price_subtotal_incl)

                # Match cart lines that this reward line applies to
                matched_cart_lines = self.env['pos.order.line']

                # 1. Match by reward_identifier_code if set on both
                rl_code = getattr(rl, 'reward_identifier_code', False)
                if rl_code:
                    matched_cart_lines = cart_lines.filtered(
                        lambda cl: getattr(cl, 'reward_identifier_code', False) == rl_code
                    )

                # 2. Match by product applicability if not matched by code
                if not matched_cart_lines:
                    if getattr(reward, 'discount_applicability', '') == 'order':
                        matched_cart_lines = cart_lines
                    else:
                        target_products = getattr(reward, 'discount_product_ids', self.env['product.product'])
                        cmr_products = getattr(reward, 'cmr_discount_product_ids', self.env['product.product'])
                        all_target_products = target_products | cmr_products

                        target_categories = getattr(reward, 'nhcl_discount_product_category_ids',
                                                    self.env['product.category'])
                        single_category = getattr(reward, 'discount_product_category_id', self.env['product.category'])
                        all_target_categories = target_categories | single_category

                        matched_cart_lines = cart_lines.filtered(
                            lambda cl: cl.product_id in all_target_products or
                                       cl.product_id.categ_id in all_target_categories
                        )

                # Fallback to all cart lines if no specific matching line found
                if not matched_cart_lines:
                    matched_cart_lines = cart_lines

                # Match by tax if the reward line has tax_ids
                if rl.tax_ids and matched_cart_lines:
                    tax_matched_cart_lines = matched_cart_lines.filtered(
                        lambda cl: set(cl.tax_ids.ids) == set(rl.tax_ids.ids)
                    )
                    if tax_matched_cart_lines:
                        matched_cart_lines = tax_matched_cart_lines

                # Calculate the percentage of discount relative to the total of matched cart lines
                if matched_cart_lines:
                    applicable_total = sum(abs(cl.price_subtotal_incl) for cl in matched_cart_lines)
                    if not applicable_total:
                        # Fallback if totals are 0
                        applicable_total = sum(abs(cl.price_unit * cl.qty) for cl in matched_cart_lines)

                    if applicable_total:
                        rl_percentage = (discount_amount / applicable_total) * 100.0
                    else:
                        rl_percentage = 0.0

                    for cl in matched_cart_lines:
                        line_vals[cl.id]['percentage'] += rl_percentage
                        if not line_vals[cl.id]['program_id']:
                            line_vals[cl.id]['program_id'] = program.id

        for line in self:
            vals = line_vals.get(line.id, {'percentage': 0.0, 'program_id': False})
            line.promo_discount_percentage = vals['percentage']
            line.applied_program_id = vals['program_id']

            line_total = abs(line.price_subtotal_incl)
            if not line_total:
                line_total = abs(line.price_unit * line.qty)

            line.promo_discount_amount = (line.promo_discount_percentage * line_total) / 100.0

    @api.depends('order_id.lines', 'order_id.lines.is_fix_discount_line', 'order_id.lines.price_subtotal_incl',
                 'order_id.lines.price_unit')
    def _compute_fix_discount(self):
        orders = self.mapped('order_id')
        discount_pct_per_order = {}
        eligible_lines_per_order = {}

        for order in orders:
            if not order:
                continue
            fix_discount_lines = order.lines.filtered(lambda l: l.is_fix_discount_line)
            if not fix_discount_lines:
                discount_pct_per_order[order.id] = 0.0
                eligible_lines_per_order[order.id] = self.env['pos.order.line']
                continue

            total_fix_discount = abs(sum(l.price_unit for l in fix_discount_lines))
            eligible_lines = order.lines.filtered(
                lambda l: not l.is_fix_discount_line and not (
                        getattr(l, 'is_reward_line', False) or
                        getattr(l, 'reward_id', False) or
                        getattr(l, 'discount_reward', False) or
                        getattr(l, 'nhcl_reward_id', False)
                )
            )
            eligible_lines_per_order[order.id] = eligible_lines

            total_eligible_value = 0.0
            for l in eligible_lines:
                res = l._compute_amount_line_all()
                total_eligible_value += res.get('price_subtotal_incl', 0.0)

            if total_eligible_value:
                discount_pct_per_order[order.id] = (total_fix_discount / total_eligible_value) * 100.0
            else:
                discount_pct_per_order[order.id] = 0.0

        for line in self:
            order = line.order_id
            if not order or order.id not in discount_pct_per_order:
                line.fix_discount_amount = 0.0
                line.fix_discount_percentage = 0.0
                continue

            eligible_lines = eligible_lines_per_order.get(order.id, self.env['pos.order.line'])
            if line in eligible_lines:
                pct = discount_pct_per_order[order.id]
                line.fix_discount_percentage = pct

                res = line._compute_amount_line_all()
                original_subtotal_incl = res.get('price_subtotal_incl', 0.0)
                line.fix_discount_amount = original_subtotal_incl * (pct / 100.0)
            else:
                line.fix_discount_amount = 0.0
                line.fix_discount_percentage = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for line in records:
            line_modified = False
            # LOT PRICE LOGIC
            if line.pack_lot_ids:
                lot = self.env['stock.lot'].search([
                    ('name', '=', line.pack_lot_ids[0].lot_name),
                    ('product_id', '=', line.pack_lot_ids[0].product_id.id)
                ], limit=1)

                if lot:
                    if lot.rs_price > 0:
                        if not (
                                line.reward_id.reward_type == 'discount' and line.reward_id.buy_with_reward_price == 'yes'):
                            line.price_unit = lot.rs_price
                            line_modified = True
                        line.nhcl_rs_price = lot.rs_price
                        line.nhcl_mr_price = lot.mr_price

                    if lot.cost_price:
                        line.nhcl_cost_price = lot.cost_price

            # REWARD LOGIC
            if line.reward_id:
                # if line.reward_id.reward_type == 'discount' and line.reward_id.buy_with_reward_price == 'yes':
                #     line.price_unit = line.reward_id.reward_price / line.reward_id.buy_product_value

                if line.reward_id.reward_type == 'discount_on_product':
                    line.price_unit = line.reward_id.product_price
                    line_modified = True

                price_unit = abs(line.price_unit)

                tax_ids = self.env['account.tax'].search([
                    ('min_amount', '<=', price_unit),
                    ('max_amount', '>=', price_unit)
                ])

                if line.reward_id.reward_product_id:
                    for tax in tax_ids:
                        product = line.reward_id.reward_product_id
                        tax_id = product.taxes_id.filtered(lambda x: x.id == tax.id)
                        if tax_id:
                            line.tax_ids = tax_id
                            line_modified = True
                            break
                elif line.is_reward_line and line.reward_id.discount_max_amount > 0 and line.reward_id.buy_with_reward_price == 'no':
                    line.tax_ids = False
                    line_modified = True

            if line_modified:
                line.update(line._compute_amount_line_all())

        return records

    def _export_for_ui(self, orderline):
        result = super()._export_for_ui(orderline)

        result['gdiscount'] = orderline.gdiscount
        result['discount_reward'] = orderline.discount_reward
        result["employe_no"] = orderline.employe_no
        result["badge_id"] = orderline.badge_id
        result["employ_id"] = orderline.employ_id.id if orderline.employ_id else False

        return result

    # def _order_line_fields(self, line, session_id=None):
    #     res = super()._order_line_fields(line, session_id)
    #     # coupon_id may be negative in case of new coupons, they will be added after validating the order.
    #     if 'coupon_id' in res[2] and res[2]['coupon_id'] and res[2]['coupon_id'] < 1:
    #         res[2].pop('coupon_id')
    #     return res

    def _compute_amount_line_all(self):
        self.ensure_one()
        fpos = self.order_id.fiscal_position_id
        tax_ids_after_fiscal_position = fpos.map_tax(self.tax_ids)
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        price = price * (1 - (self.gdiscount or 0.0) / 100.0)
        if getattr(self, 'discount_fix', 0.0):
            price -= self.discount_fix
        taxes = tax_ids_after_fiscal_position.compute_all(
            price,
            self.order_id.currency_id,
            self.qty,
            product=self.product_id,
            partner=self.order_id.partner_id
        )
        return {
            'price_subtotal_incl': taxes['total_included'],
            'price_subtotal': taxes['total_excluded'],
        }

    @api.onchange('qty', 'discount', 'price_unit', 'tax_ids', 'gdiscount', 'discount_fix')
    def _onchange_qty(self):
        if self.product_id:
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            price = price * (1 - (self.gdiscount or 0.0) / 100.0)
            if getattr(self, 'discount_fix', 0.0):
                price -= self.discount_fix
            self.price_subtotal = self.price_subtotal_incl = price * self.qty
            if self.tax_ids:
                taxes = self.tax_ids.compute_all(price, self.order_id.currency_id, self.qty, product=self.product_id,
                                                 partner=False)
                self.price_subtotal = taxes['total_excluded']
                self.price_subtotal_incl = taxes['total_included']


class PosOrder(models.Model):
    _inherit = 'pos.order'

    _rec_name = 'pos_reference'

    editable_payment_ids = fields.One2many('pos.payment', 'pos_order_id', string='MOP Change')
    credit_note_count = fields.Integer(
        compute="_compute_credit_note_count",
        string="Credit Notes"
    )
    amount_discount = fields.Float(compute="compute_amount_discount", string="Manual Discount", store=True)
    amount_reward_discount = fields.Float(compute="compute_amount_discount", string="Promo Discount", store=True)
    amount_untaxed = fields.Float(compute="compute_amount_untaxed", string="Untaxed Amount", store=True)

    @api.depends('lines', 'lines.gdiscount', 'lines.discount', 'lines.is_fix_discount_line',
                 'lines.total_discount', 'lines.total_reward_discount')
    def compute_amount_discount(self):
        for order in self:
            lines = order.lines.filtered(lambda line: not line.is_fix_discount_line)
            order.amount_reward_discount = sum(lines.mapped('total_reward_discount'))
            # order.amount_discount = sum(lines.mapped('total_discount')) + sum(lines.mapped('fix_discount_amount'))
            order.amount_discount = sum(lines.mapped('total_discount'))
            # lines = order.lines.filtered(lambda line: line.is_fix_discount_line)
            # order.amount_discount += -sum(lines.mapped('price_unit'))

    @api.depends('amount_total', 'amount_tax')
    def compute_amount_untaxed(self):
        for order in self:
            order.amount_untaxed = order.amount_total - order.amount_tax

    # def _process_order(self, order, draft, existing_order):
    #     res = super()._process_order(order, draft, existing_order)
    #     created_order = self.browse(res).exists()
    #     if created_order and created_order.amount_paid:
    #         created_order.amount_total = created_order.amount_paid
    #     return res
    #
    # def _prepare_refund_values(self, current_session):
    #     self.ensure_one()
    #     res = super()._prepare_refund_values(current_session)
    #     res.update({
    #         'amount_total': sum(self.lines.mapped('price_subtotal_incl')),
    #     })
    #     return res

    def _get_invoice_lines_values(self, line_values, pos_line):
        inv_line_vals = super()._get_invoice_lines_values(line_values, pos_line)

        inv_line_vals.update({
            'gdiscount': pos_line.gdiscount,
            'discount': inv_line_vals['discount'] + pos_line.gdiscount,
        })

        return inv_line_vals

    def _compute_credit_note_count(self):
        for order in self:
            picking = self.env['stock.picking'].search([
                ('nhcl_pos_order', '=', order.pos_reference),
                ('ref_credit_note', '!=', False),
            ], limit=1)

            if picking and picking.ref_credit_note:
                order.credit_note_count = 1
            else:
                order.credit_note_count = 0

    def action_view_credit_notes(self):
        self.ensure_one()

        picking = self.env['stock.picking'].search([
            ('nhcl_pos_order', '=', self.pos_reference),
            ('ref_credit_note', '!=', False),
        ], limit=1)

        if not picking:
            return

        credit_note = picking.ref_credit_note  # This is account.move record

        return {
            'name': 'Credit Note',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'context': {'create': False},
        }

    credit_id = fields.Integer("Credit Id")
    credit_ids = fields.One2many('used.credits', 'used_credit_id', string='Credits', copy=False)

    def _create_invoice(self, move_vals):
        """Override for the rounding issue"""
        self.ensure_one()
        self._recalculate_order_lines_and_totals()
        new_move = self.env['account.move'].sudo().with_company(self.company_id).with_context(
            default_move_type=move_vals['move_type']).create(move_vals)
        self._synchronize_invoice(new_move)
        message = _("This invoice has been created from the point of sale session: %s",
                    self._get_html_link())

        new_move.message_post(body=message)
        return new_move

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        credit_ids = ui_order.get('credit_ids', [])
        credit_amounts = ui_order.get('credit_note_amounts', [])
        credit_lines = []
        existing_credit_notes = []
        for credit_id, amount in zip(credit_ids, credit_amounts):
            if credit_id not in existing_credit_notes:
                credit_lines.append((0, 0, {
                    'credit_id': int(credit_id),
                    'amount': amount,
                }))
                existing_credit_notes.append(credit_id)
        order_fields['credit_ids'] = credit_lines
        return order_fields

    @api.model_create_multi
    def create(self, vals_list):
        orders = super(PosOrder, self).create(vals_list)
        orders._recalculate_order_lines_and_totals()

        for order in orders:

            # CREDIT LINKING
            for credit in order.credit_ids:
                credit.used_credit_id = order.id

            reward_order_lines = order.lines.filtered(lambda x: x.reward_id)
            discount_reward_order_lines = order.lines.filtered(lambda x: x.discount_reward > 0)
            remaining_order_lines = order.lines.filtered(lambda x: not x.reward_id)

            # 🎯 REWARD PROCESSING
            for reward_order_line in reward_order_lines:
                reward = reward_order_line.reward_id

                if reward.program_id.is_vendor_return:

                    # CASE 1: PRODUCT REWARD
                    if (
                            reward.reward_type == 'product' and
                            reward.reward_product_id in reward.program_id.rule_ids.ref_product_ids
                    ):
                        free_qty = reward.reward_product_qty
                        count = 0

                        for line in remaining_order_lines:
                            if reward.reward_product_id == line.product_id and count < free_qty:
                                line.vendor_return_disc_price = line.price_unit
                                count += 1

                    # CASE 2: ORDER DISCOUNT
                    elif reward.discount_applicability == 'order':
                        total_qty = sum(remaining_order_lines.mapped('qty'))

                        if reward_order_line.price_unit > 0 and total_qty > 0:
                            price = reward_order_line.price_unit / total_qty

                            for line in remaining_order_lines:
                                line.vendor_return_disc_price += line.qty * -price

                    # CASE 3: SERIAL BASED
                    else:
                        rewards = reward.program_id.reward_ids
                        reward_index = rewards.ids.index(reward.id)

                        if reward.program_id.rule_ids:
                            serial_names = reward.program_id.rule_ids[
                                reward_index
                            ].serial_ids.mapped('name')

                            serial_lines = remaining_order_lines.pack_lot_ids.filtered(
                                lambda x: x.lot_name in serial_names
                            )

                            total_qty = len(serial_lines)

                            if reward_order_line.price_unit > 0 and total_qty > 0:
                                price = reward_order_line.price_unit / total_qty

                                for line in remaining_order_lines:
                                    for lot in line.pack_lot_ids:
                                        if lot.lot_name in serial_names:
                                            line.vendor_return_disc_price += line.qty * -price

            # DISCOUNT REWARD PROCESSING
            for line in discount_reward_order_lines:
                reward = self.env['loyalty.reward'].browse(line.discount_reward)

                if reward.program_id.is_vendor_return:
                    if reward.discount_applicability == 'specific' and reward.discount > 0:
                        discount = reward.discount / 100
                        price = line.price_unit * discount
                        line.vendor_return_disc_price = price

        return orders

    def _serial_pos_post(self):
        stock_lot = self.env['stock.lot']
        lot_names = set()  # Use a set to collect lot names

        for order in self:
            for line in order.lines:
                for lot in line.pack_lot_ids:
                    lot_names.add(lot.lot_name)

        # Retrieve all stock.lot records that match the lot names in a single search
        stock_lots = stock_lot.search([('name', 'in', list(lot_names))])

        # Create a dictionary of lot names to stock lot records
        lot_dict = {lot.name: lot for lot in stock_lots}

        # Now, loop through the orders and lines and update the stock lots in batch
        for order in self:
            for line in order.lines:
                for lot in line.pack_lot_ids:

                    lot_name = lot.lot_name
                    lot = lot_dict.get(lot_name)
                    if lot and lot.product_qty == 1:
                        lot.write({'is_used': True})

    def _process_saved_order(self, draft):
        self._recalculate_order_lines_and_totals()
        res = super(PosOrder, self)._process_saved_order(draft)
        ## OLD Code of other
        # if self.state == 'paid':
        # NEW Pranav Start
        if self.state in ['paid', 'invoiced', 'done']:
            #  STOP
            self._serial_pos_post()
            existing_credit_notes = []
            for credit_id in self.credit_ids:
                credit = self.partner_id.credit_note_ids.filtered(lambda x: x.id == credit_id.credit_id)
                if credit and credit.id not in existing_credit_notes:
                    credit.write({'deducted_amount': credit.deducted_amount + credit_id.amount})
                    existing_credit_notes.append(credit.id)
        return res

    @api.model
    def remove_from_ui(self, server_ids):
        # Find draft orders before other overrides (like pos_self_order) change their state to 'cancel'
        draft_orders = self.search([('id', 'in', server_ids), ('state', '=', 'draft')])

        # Call super to let Odoo process normal cancellation notifications and actions
        res = super().remove_from_ui(server_ids)

        # Explicitly delete the draft orders so they do not remain in the database
        if draft_orders:
            draft_orders.mapped('payment_ids').sudo().unlink()
            draft_orders.sudo().unlink()

        return res

    def confirm_coupon_programs(self, coupon_data):
        """
        This is called after the order is created.

        This will create all necessary coupons and link them to their line orders etc..

        It will also return the points of all concerned coupons to be updated in the cache.
        """
        get_partner_id = lambda partner_id: partner_id and self.env['res.partner'].browse(
            partner_id).exists() and partner_id or False
        # Keys are stringified when using rpc
        coupon_data = {int(k): v for k, v in coupon_data.items()}

        self._check_existing_loyalty_cards(coupon_data)
        # Map negative id to newly created ids.
        coupon_new_id_map = {k: k for k in coupon_data.keys() if k > 0}

        # Create the coupons that were awarded by the order.
        coupons_to_create = {k: v for k, v in coupon_data.items() if k < 0 and not v.get('giftCardId')}
        coupon_create_vals = [{
            'program_id': p['program_id'],
            'partner_id': get_partner_id(p.get('partner_id', False)),
            'code': p.get('barcode') or self.env['loyalty.card']._generate_code(),
            'points': 0,
            'source_pos_order_id': self.id,
        } for p in coupons_to_create.values()]

        # Pos users don't have the create permission
        new_coupons = self.env['loyalty.card'].with_context(action_no_send_mail=True).sudo().create(coupon_create_vals)

        # We update the gift card that we sold when the gift_card_settings = 'scan_use'.
        gift_cards_to_update = [v for v in coupon_data.values() if v.get('giftCardId')]
        updated_gift_cards = self.env['loyalty.card']
        for coupon_vals in gift_cards_to_update:
            gift_card = self.env['loyalty.card'].browse(coupon_vals.get('giftCardId'))
            print("1", gift_card)
            gift_card.write({
                'points': coupon_vals['points'],
                'source_pos_order_id': self.id,
                'partner_id': get_partner_id(coupon_vals.get('partner_id', False)),
            })
            updated_gift_cards |= gift_card

        # Map the newly created coupons
        for old_id, new_id in zip(coupons_to_create.keys(), new_coupons):
            coupon_new_id_map[new_id.id] = old_id

        all_coupons = self.env['loyalty.card'].browse(coupon_new_id_map.keys()).exists()
        lines_per_reward_code = defaultdict(lambda: self.env['pos.order.line'])
        for line in self.lines:
            if not line.reward_identifier_code:
                continue
            lines_per_reward_code[line.reward_identifier_code] |= line
        for coupon in all_coupons:
            if coupon.id in coupon_new_id_map:
                # Coupon existed previously, update amount of points.
                coupon.points += coupon_data[coupon_new_id_map[coupon.id]]['points']
                coupon.nhcl_used_card = True
            for reward_code in coupon_data[coupon_new_id_map[coupon.id]].get('line_codes', []):
                lines_per_reward_code[reward_code].coupon_id = coupon
        # Send creation email
        new_coupons.with_context(action_no_send_mail=False)._send_creation_communication()
        # Reports per program
        report_per_program = {}
        coupon_per_report = defaultdict(list)
        # Important to include the updated gift cards so that it can be printed. Check coupon_report.
        for coupon in new_coupons | updated_gift_cards:
            if coupon.program_id not in report_per_program:
                report_per_program[coupon.program_id] = coupon.program_id.communication_plan_ids. \
                    filtered(lambda c: c.trigger == 'create').pos_report_print_id
            for report in report_per_program[coupon.program_id]:
                coupon_per_report[report.id].append(coupon.id)
        return {
            'coupon_updates': [{
                'old_id': coupon_new_id_map[coupon.id],
                'id': coupon.id,
                'points': coupon.points,
                'code': coupon.code,
                'program_id': coupon.program_id.id,
                'partner_id': coupon.partner_id.id,
            } for coupon in all_coupons if coupon.program_id.is_nominative],
            'program_updates': [{
                'program_id': program.id,
                'usages': program.total_order_count,
            } for program in all_coupons.program_id],
            'new_coupon_info': [{
                'program_name': coupon.program_id.name,
                'expiration_date': coupon.expiration_date,
                'code': coupon.code,
            } for coupon in new_coupons if (
                    coupon.program_id.applies_on == 'future'
                    # Don't send the coupon code for the gift card and ewallet programs.
                    # It should not be printed in the ticket.
                    and coupon.program_id.program_type not in ['gift_card', 'ewallet']
            )],
            'coupon_report': coupon_per_report,
        }

    def update_credit_voucher_to_customer(self, partner_id=None):
        partner = self.env['res.partner'].browse(partner_id)
        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        if ho_id:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            api_key = ho_id.nhcl_api_key
            headers_source = {'api_key': f"{api_key}", 'Content_Type': 'application/json'}
            try:
                # -------------------- Customer --------------------
                customer_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                customer_domain = [('name', '=', partner.name), ('phone', '=', partner.phone)]
                customer_url = f"{customer_search}?domain={customer_domain}"
                customer_get_data = requests.get(customer_url, headers=headers_source).json()
                customer_data = customer_get_data.get("data")
                # -------------------- Customer Credit Note --------------------
                customer_credit_notes = f"http://{ho_ip}:{ho_port}/api/res.partner.credit.note/search"
                customer_credit_notes_domain = [('partner_id', '=', customer_data[0]['id'])]
                customer_credit_notes_url = f"{customer_credit_notes}?domain={customer_credit_notes_domain}"
                customer_get_credit_notes_data = requests.get(customer_credit_notes_url, headers=headers_source).json()
                customer_credit_notes_data = customer_get_credit_notes_data.get("data")
                for each in customer_credit_notes_data:
                    exiting_vocher = partner.credit_note_ids.filtered(
                        lambda x: x.voucher_number == each['voucher_number'])
                    if not exiting_vocher:
                        partner.credit_note_ids.create({
                            'voucher_number': each['voucher_number'],
                            'pos_bill_number': each['pos_bill_number'],
                            'pos_bill_date': each['pos_bill_date'],
                            'total_amount': each['total_amount'],
                            'deducted_amount': each['deducted_amount'],
                            'partner_id': partner.id,
                        })
                    print("customer_credit_notes_data", each['voucher_number'])
            except Exception as e:
                msg = f"Unexpected error while processing {self.name}: {e}"
                ho_id.create_cmr_transaction_server_replication_log("failure", msg)

    def _recalculate_order_lines_and_totals(self):
        for order in self:
            # 0. Resolve taxes from lot if line has no taxes and has pack_lot_ids
            for line in order.lines:
                if not line.tax_ids and line.pack_lot_ids:
                    lot = self.env['stock.lot'].search([
                        ('name', '=', line.pack_lot_ids[0].lot_name),
                        ('product_id', '=', line.pack_lot_ids[0].product_id.id)
                    ], limit=1)
                    if lot and lot.sale_tax_ids:
                        price_unit = line.price_unit * (1.0 - (line.discount / 100.0))
                        selected_tax = self.env['account.tax']
                        if len(lot.sale_tax_ids) == 1:
                            selected_tax = lot.sale_tax_ids[0]
                        else:
                            for tax in lot.sale_tax_ids:
                                min_val = tax.min_amount or 0.0
                                max_val = tax.max_amount or 0.0
                                if min_val == 0.0 and max_val == 0.0:
                                    tax_amount = sum(child.amount for child in
                                                     tax.children_tax_ids) if tax.amount_type == 'group' else tax.amount
                                    if tax_amount == 5.0:
                                        min_val = 0.0
                                        max_val = 1000.0
                                    elif tax_amount in (12.0, 18.0):
                                        min_val = 1000.01
                                        max_val = 99999999.0
                                if min_val <= price_unit <= max_val:
                                    selected_tax = tax
                                    break
                            if not selected_tax:
                                selected_tax = lot.sale_tax_ids[0]
                        if selected_tax:
                            line.write({'tax_ids': [(6, 0, selected_tax.ids)]})

            # 1. Recalculate taxes for reward/discount lines
            reward_lines_by_reward = defaultdict(lambda: self.env['pos.order.line'])
            for line in order.lines:
                if line.reward_id and not line.reward_id.reward_product_id:
                    reward_lines_by_reward[line.reward_id] |= line

            for reward_id, r_lines in reward_lines_by_reward.items():
                sibling_by_r_line = {}
                for r_line in r_lines:
                    parsed_ids = []
                    if r_line.disc_lines:
                        try:
                            import ast
                            parsed_list = ast.literal_eval(r_line.disc_lines)
                            if isinstance(parsed_list, list):
                                for x in parsed_list:
                                    if isinstance(x, (int, float)):
                                        parsed_ids.append(int(x))
                                    elif isinstance(x, str) and x.isdigit():
                                        parsed_ids.append(int(x))
                        except Exception:
                            pass

                    sibling_lines = order.lines.filtered(
                        lambda l: not l.reward_id and (
                                l.product_id.id in parsed_ids or
                                l.product_id.nhcl_id in parsed_ids or
                                str(l.product_id.id) in parsed_ids or
                                str(l.product_id.nhcl_id) in parsed_ids
                        )
                    )
                    if not sibling_lines:
                        sibling_lines = order.lines.filtered(lambda l: not l.reward_id)

                    sibling_by_r_line[r_line] = sibling_lines

                assigned_siblings = self.env['pos.order.line']
                r_line_taxes = {}

                # Pass 1: Exact tax match
                unmatched_r_lines = []
                for r_line in r_lines:
                    current_taxes = r_line.tax_ids
                    siblings = sibling_by_r_line[r_line]
                    exact_match_siblings = siblings.filtered(lambda s: s.tax_ids == current_taxes)
                    if exact_match_siblings:
                        r_line_taxes[r_line] = exact_match_siblings.mapped('tax_ids')
                        assigned_siblings |= exact_match_siblings
                    else:
                        unmatched_r_lines.append(r_line)

                # Pass 2: Intersecting tax match
                still_unmatched = []
                for r_line in unmatched_r_lines:
                    current_taxes = r_line.tax_ids
                    siblings = sibling_by_r_line[r_line]
                    available_siblings = siblings - assigned_siblings
                    intersect_match_siblings = available_siblings.filtered(lambda s: s.tax_ids & current_taxes)
                    if intersect_match_siblings:
                        r_line_taxes[r_line] = intersect_match_siblings.mapped('tax_ids')
                        assigned_siblings |= intersect_match_siblings
                    else:
                        still_unmatched.append(r_line)

                # Pass 3: Fallback match
                for r_line in still_unmatched:
                    siblings = sibling_by_r_line[r_line]
                    available_siblings = siblings - assigned_siblings
                    if not available_siblings:
                        available_siblings = siblings

                    if available_siblings:
                        first_sibling = available_siblings[0]
                        r_line_taxes[r_line] = first_sibling.tax_ids
                        assigned_siblings |= first_sibling
                    else:
                        r_line_taxes[r_line] = r_line.tax_ids

                for r_line, taxes in r_line_taxes.items():
                    if taxes:
                        r_line.write({'tax_ids': [(6, 0, taxes.ids)]})

            # 2. Recalculate subtotals on all lines (using standard calculations first)
            for line in order.lines:
                line.write(line._compute_amount_line_all())
            order.lines._compute_promo_discount()
            order.lines._compute_fix_discount()

            # Conditionally adjust subtotals and zero out manual discount lines if the discount was divided
            has_fix_discount_division = any(
                line.fix_discount_amount for line in order.lines if not line.is_fix_discount_line)
            if has_fix_discount_division:
                for line in order.lines:
                    if line.is_fix_discount_line:
                        line.write({'qty': 0.0, 'price_subtotal': 0.0, 'price_subtotal_incl': 0.0})

                # Adjust subtotals for lines with fix_discount_amount
                for line in order.lines:
                    if not line.is_fix_discount_line and line.fix_discount_amount:
                        subtotal_incl = line.price_subtotal_incl
                        new_subtotal_incl = subtotal_incl - line.fix_discount_amount
                        currency = order.currency_id or line.company_id.currency_id

                        if line.tax_ids:
                            tax_results = line.tax_ids.compute_all(
                                new_subtotal_incl,
                                currency=currency,
                                quantity=1.0,
                                product=line.product_id,
                                partner=order.partner_id
                            )
                            new_subtotal = tax_results['total_excluded']
                        else:
                            new_subtotal = new_subtotal_incl

                        line.write({
                            'price_subtotal_incl': currency.round(new_subtotal_incl) if currency else new_subtotal_incl,
                            'price_subtotal': currency.round(new_subtotal) if currency else new_subtotal,
                        })

            # 3. Recalculate order totals
            order._compute_batch_amount_all()
            order.compute_amount_discount()

            # Apply cash rounding to order.amount_total and order.amount_tax to align with invoice cash rounding
            if order.config_id.cash_rounding and (not order.config_id.only_round_cash_method or any(
                    p.payment_method_id.is_cash_count for p in order.payment_ids)):
                raw_total = order.amount_total
                rounding_precision = order.config_id.rounding_method.rounding

                # If amount_paid is close to raw_total within rounding precision, use it directly to avoid JS vs Python rounding mismatches
                if order.amount_paid and abs(order.amount_paid - raw_total) <= (rounding_precision + 0.05):
                    rounded_total = order.amount_paid
                else:
                    rounded_total = float_round(
                        raw_total,
                        precision_rounding=rounding_precision,
                        rounding_method=order.config_id.rounding_method.rounding_method
                    )
                rounding_applied = rounded_total - raw_total
                order.write({
                    'amount_total': rounded_total,
                    'amount_tax': order.currency_id.round(
                        order.amount_tax + rounding_applied) if order.currency_id else order.amount_tax + rounding_applied,
                })

            order.compute_amount_untaxed()

    def _synchronize_invoice(self, invoice, was_posted=None):
        self.ensure_one()
        if not invoice:
            return

        # Reset invoice to draft if it's posted
        is_posted = was_posted if was_posted is not None else (invoice.state == 'posted')
        if invoice.state == 'posted':
            invoice.line_ids.remove_move_reconcile()
            invoice.with_context(skip_invoice_sync=True, check_move_validity=False).button_draft()

        # Get product/invoice lines (filtered out notes/section lines)
        inv_lines = invoice.invoice_line_ids.filtered(lambda l: not l.display_type or l.display_type == 'product')

        # Match by product_id
        pos_lines_by_product = defaultdict(list)
        for line in self.lines:
            pos_lines_by_product[line.product_id.id].append(line)

        inv_lines_by_product = defaultdict(list)
        for line in inv_lines:
            inv_lines_by_product[line.product_id.id].append(line)

        lines_to_delete = self.env['account.move.line']
        is_refund = invoice.move_type == 'out_refund'

        all_product_ids = set(pos_lines_by_product.keys()) | set(inv_lines_by_product.keys())

        for prod_id in all_product_ids:
            p_lines = pos_lines_by_product[prod_id]
            i_lines = inv_lines_by_product[prod_id]

            for idx in range(max(len(p_lines), len(i_lines))):
                if idx < len(p_lines) and idx < len(i_lines):
                    # Update existing line
                    order_line = p_lines[idx]
                    inv_line = i_lines[idx]

                    inv_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                        'quantity': order_line.qty,
                        'price_unit': order_line.price_unit,
                        'discount': order_line.discount + getattr(order_line, 'gdiscount', 0.0) + getattr(order_line,
                                                                                                          'fix_discount_percentage',
                                                                                                          0.0),
                        'tax_ids': [(6, 0, order_line.tax_ids.ids)],
                        'gdiscount': getattr(order_line, 'gdiscount', 0.0),
                        'discount_fix': getattr(order_line, 'discount_fix', 0.0),
                        'discount_percentage': getattr(order_line, 'discount_percentage', 0.0),
                        'fix_discount_amount': getattr(order_line, 'fix_discount_amount', 0.0),
                        'fix_discount_percentage': getattr(order_line, 'fix_discount_percentage', 0.0),
                    })

                    # Force custom computed subtotals:
                    inv_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                        'price_subtotal': order_line.price_subtotal,
                        'price_total': order_line.price_subtotal_incl,
                    })

                    # Update credit/debit
                    balance = -order_line.price_subtotal
                    if is_refund:
                        balance = -balance

                    if balance >= 0:
                        inv_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                            'debit': balance,
                            'credit': 0.0,
                            'balance': balance,
                            'amount_currency': balance,
                        })
                    else:
                        inv_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                            'debit': 0.0,
                            'credit': -balance,
                            'balance': balance,
                            'amount_currency': balance,
                        })
                elif idx < len(i_lines):
                    # Extra invoice line, delete it
                    lines_to_delete |= i_lines[idx]
                else:
                    # Missing invoice line, create it
                    order_line = p_lines[idx]

                    balance = -order_line.price_subtotal
                    if is_refund:
                        balance = -balance

                    new_line_vals = {
                        'move_id': invoice.id,
                        'product_id': order_line.product_id.id,
                        'quantity': order_line.qty,
                        'price_unit': order_line.price_unit,
                        'name': order_line.product_id.display_name,
                        'product_uom_id': order_line.product_uom_id.id,
                        'discount': order_line.discount + getattr(order_line, 'gdiscount', 0.0) + getattr(order_line,
                                                                                                          'fix_discount_percentage',
                                                                                                          0.0),
                        'tax_ids': [(6, 0, order_line.tax_ids.ids)],
                        'gdiscount': getattr(order_line, 'gdiscount', 0.0),
                        'discount_fix': getattr(order_line, 'discount_fix', 0.0),
                        'discount_percentage': getattr(order_line, 'discount_percentage', 0.0),
                        'fix_discount_amount': getattr(order_line, 'fix_discount_amount', 0.0),
                        'fix_discount_percentage': getattr(order_line, 'fix_discount_percentage', 0.0),
                        'price_subtotal': order_line.price_subtotal,
                        'price_total': order_line.price_subtotal_incl,
                        'debit': balance >= 0.0 and balance or 0.0,
                        'credit': balance < 0.0 and -balance or 0.0,
                        'balance': balance,
                        'amount_currency': balance,
                    }
                    self.env['account.move.line'].with_context(skip_invoice_sync=True,
                                                               check_move_validity=False).create(new_line_vals)

        if lines_to_delete:
            lines_to_delete.with_context(skip_invoice_sync=True, check_move_validity=False).unlink()

        # Sum up the tax amounts per tax_id from the order lines (handling group taxes by flattening them)
        def get_leaf_taxes(taxes):
            res = []
            for t in taxes:
                if t.amount_type == 'group':
                    res.extend(get_leaf_taxes(t.children_tax_ids))
                else:
                    res.append(t)
            return res

        tax_totals = defaultdict(float)
        currency = invoice.currency_id
        for order_line in self.lines:
            tax_amount = currency.round(order_line.price_subtotal_incl - order_line.price_subtotal)
            leaf_taxes = get_leaf_taxes(order_line.tax_ids)
            if leaf_taxes:
                total_tax_amount_rate = sum(t.amount for t in leaf_taxes)
                if total_tax_amount_rate:
                    distributed_sum = 0.0
                    for i, tax in enumerate(leaf_taxes):
                        if i < len(leaf_taxes) - 1:
                            share = currency.round(tax_amount * (tax.amount / total_tax_amount_rate))
                            tax_totals[tax.id] += share
                            distributed_sum += share
                        else:
                            share = currency.round(tax_amount - distributed_sum)
                            tax_totals[tax.id] += share
                else:
                    distributed_sum = 0.0
                    for i, tax in enumerate(leaf_taxes):
                        if i < len(leaf_taxes) - 1:
                            share = currency.round(tax_amount / len(leaf_taxes))
                            tax_totals[tax.id] += share
                            distributed_sum += share
                        else:
                            share = currency.round(tax_amount - distributed_sum)
                            tax_totals[tax.id] += share

        # Adjust tax totals by cash rounding difference to avoid creating cash rounding lines
        if self.config_id.cash_rounding and tax_totals:
            raw_total = sum(line.price_subtotal_incl for line in self.lines)
            rounding_applied = float_round(self.amount_total - raw_total,
                                           precision_rounding=invoice.currency_id.rounding)
            if rounding_applied:
                largest_tax_id = max(tax_totals, key=lambda k: abs(tax_totals[k]))
                tax_totals[largest_tax_id] = float_round(tax_totals[largest_tax_id] + rounding_applied,
                                                         precision_rounding=invoice.currency_id.rounding)

        # Update the tax lines in the journal entry
        existing_tax_lines = invoice.line_ids.filtered(lambda l: l.display_type == 'tax')
        used_tax_lines = self.env['account.move.line']

        for tax_id, tax_amount in tax_totals.items():
            balance = -tax_amount
            if is_refund:
                balance = -balance

            tax_record = self.env['account.tax'].browse(tax_id)
            rep_lines = tax_record.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax')
            rep_line_id = rep_lines and rep_lines[0].id
            account_id = rep_lines and rep_lines[0].account_id.id

            tax_line = existing_tax_lines.filtered(
                lambda l: (l.tax_line_id.id == tax_id) or (rep_line_id and l.tax_repartition_line_id.id == rep_line_id)
            )
            if tax_line:
                tax_line = tax_line[0]
                used_tax_lines |= tax_line
                write_vals = {
                    'tax_line_id': tax_id,
                    'tax_repartition_line_id': rep_line_id,
                    'balance': balance,
                    'amount_currency': balance,
                }
                if balance >= 0:
                    write_vals.update({'debit': balance, 'credit': 0.0})
                else:
                    write_vals.update({'debit': 0.0, 'credit': -balance})
                tax_line.with_context(skip_invoice_sync=True, check_move_validity=False).write(write_vals)
            else:
                if account_id:
                    new_line = self.env['account.move.line'].with_context(skip_invoice_sync=True,
                                                                          check_move_validity=False).create({
                        'move_id': invoice.id,
                        'name': tax_record.name,
                        'tax_line_id': tax_id,
                        'tax_repartition_line_id': rep_line_id,
                        'display_type': 'tax',
                        'account_id': account_id,
                        'debit': balance >= 0.0 and balance or 0.0,
                        'credit': balance < 0.0 and -balance or 0.0,
                        'balance': balance,
                        'amount_currency': balance,
                    })
                    used_tax_lines |= new_line

        # Remove unused tax lines
        unused_tax_lines = existing_tax_lines - used_tax_lines
        if unused_tax_lines:
            unused_tax_lines.with_context(skip_invoice_sync=True, check_move_validity=False,
                                          dynamic_unlink=True).unlink()

        # Update cash rounding line
        rounding_line = invoice.line_ids.filtered(lambda line: line.display_type == 'rounding')
        rounding_applied = 0.0
        if self.config_id.cash_rounding:
            rounding_applied = float_round(self.amount_paid - self.amount_total,
                                           precision_rounding=invoice.currency_id.rounding)
            if invoice.move_type == 'out_invoice':
                rounding_applied = invoice.tax_totals.get('rounding_amount', rounding_applied)

        if rounding_applied:
            balance = -rounding_applied
            if is_refund:
                balance = -balance

            if rounding_line:
                if balance >= 0:
                    rounding_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                        'debit': balance,
                        'credit': 0.0,
                        'balance': balance,
                        'amount_currency': balance,
                        'price_unit': rounding_applied,
                    })
                else:
                    rounding_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                        'debit': 0.0,
                        'credit': -balance,
                        'balance': balance,
                        'amount_currency': balance,
                        'price_unit': rounding_applied,
                    })
            else:
                if rounding_applied > 0.0:
                    account_id = invoice.invoice_cash_rounding_id.loss_account_id.id
                else:
                    account_id = invoice.invoice_cash_rounding_id.profit_account_id.id
                if not account_id and invoice.invoice_cash_rounding_id:
                    account_id = invoice.invoice_cash_rounding_id.profit_account_id.id or invoice.invoice_cash_rounding_id.loss_account_id.id
                if account_id:
                    self.env['account.move.line'].with_context(skip_invoice_sync=True,
                                                               check_move_validity=False).create({
                        'move_id': invoice.id,
                        'name': self.config_id.rounding_method.name,
                        'display_type': 'rounding',
                        'quantity': 1.0,
                        'partner_id': invoice.partner_id.id,
                        'account_id': account_id,
                        'debit': balance >= 0.0 and balance or 0.0,
                        'credit': balance < 0.0 and -balance or 0.0,
                        'balance': balance,
                        'amount_currency': balance,
                        'price_unit': rounding_applied,
                    })
        else:
            if rounding_line:
                rounding_line.with_context(skip_invoice_sync=True, check_move_validity=False).unlink()

        # Update the receivable line in the journal entry to perfectly balance the move
        receivable_lines = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        if receivable_lines:
            target_line = receivable_lines[0]
            other_lines = invoice.line_ids - target_line
            other_balance = sum(other_lines.mapped('balance'))

            target_balance = -other_balance
            currency = invoice.currency_id
            if currency:
                target_balance = currency.round(target_balance)

            if target_balance >= 0:
                target_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                    'debit': target_balance,
                    'credit': 0.0,
                    'balance': target_balance,
                    'amount_currency': target_balance,
                })
            else:
                target_line.with_context(skip_invoice_sync=True, check_move_validity=False).write({
                    'debit': 0.0,
                    'credit': -target_balance,
                    'balance': target_balance,
                    'amount_currency': target_balance,
                })

        # Force recomputing of tax totals widget to align with actual tax lines
        invoice._compute_tax_totals()

        # Re-post the invoice if it was posted
        if is_posted:
            invoice.with_context(skip_invoice_sync=True, check_move_validity=True).action_post()

            # Re-reconcile payments with the invoice
            receivable_account = self.env["res.partner"]._find_accounting_partner(self.partner_id).with_company(
                self.company_id).property_account_receivable_id
            if receivable_account.reconcile:
                invoice_receivables = invoice.line_ids.filtered(
                    lambda line: line.account_id == receivable_account and not line.reconciled)
                if invoice_receivables:
                    payment_moves = self.payment_ids.account_move_id
                    if not payment_moves:
                        payment_moves = self.env['account.move'].search([
                            ('ref', 'like', f'Invoice payment for {self.name} %')
                        ])
                    if payment_moves:
                        payment_receivables = payment_moves.line_ids.filtered(
                            lambda line: line.account_id == receivable_account and not line.reconciled
                        )
                        if payment_receivables:
                            (invoice_receivables | payment_receivables).sudo().with_company(
                                self.company_id).with_context(skip_invoice_sync=True).reconcile()

    def action_recalculate_taxes(self):
        for order in self:
            # 1. Find and split separate reward lines
            reward_lines = order.lines.filtered(
                lambda l: getattr(l, 'is_reward_line', False) and not getattr(l, 'is_fix_discount_line',
                                                                              False) and l.qty != 0 and l.price_unit != 0
            )
            cart_lines = order.lines.filtered(
                lambda l: not getattr(l, 'is_reward_line', False) and not getattr(l, 'is_fix_discount_line', False)
            )

            invoice = order.account_move
            was_posted = invoice and invoice.state == 'posted'
            lines_to_unlink = self.env['pos.order.line']

            if reward_lines and cart_lines:
                if was_posted:
                    invoice.line_ids.remove_move_reconcile()
                    invoice.with_context(skip_invoice_sync=True, check_move_validity=False).button_draft()

                for rl in reward_lines:
                    reward = getattr(rl, 'reward_id', self.env['loyalty.reward'])
                    if not reward:
                        reward = getattr(rl, 'nhcl_reward_id', self.env['loyalty.reward'])
                    if not reward or reward.reward_type not in ('discount', 'discount_on_product'):
                        continue

                    # Match cart lines that this reward line applies to
                    matched_cart_lines = self.env['pos.order.line']
                    rl_code = getattr(rl, 'reward_identifier_code', False)
                    if rl_code:
                        matched_cart_lines = cart_lines.filtered(
                            lambda cl: getattr(cl, 'reward_identifier_code', False) == rl_code
                        )

                    if not matched_cart_lines:
                        if getattr(reward, 'discount_applicability', '') == 'order':
                            matched_cart_lines = cart_lines
                        else:
                            target_products = getattr(reward, 'discount_product_ids', self.env['product.product'])
                            cmr_products = getattr(reward, 'cmr_discount_product_ids', self.env['product.product'])
                            all_target_products = target_products | cmr_products

                            target_categories = getattr(reward, 'nhcl_discount_product_category_ids',
                                                        self.env['product.category'])
                            single_category = getattr(reward, 'discount_product_category_id',
                                                      self.env['product.category'])
                            all_target_categories = target_categories | single_category

                            matched_cart_lines = cart_lines.filtered(
                                lambda cl: cl.product_id in all_target_products or
                                           cl.product_id.categ_id in all_target_categories
                            )

                    if not matched_cart_lines:
                        matched_cart_lines = cart_lines

                    if rl.tax_ids and matched_cart_lines:
                        tax_matched_cart_lines = matched_cart_lines.filtered(
                            lambda cl: set(cl.tax_ids.ids) == set(rl.tax_ids.ids)
                        )
                        if tax_matched_cart_lines:
                            matched_cart_lines = tax_matched_cart_lines

                    if matched_cart_lines:
                        applicable_total = sum(cl.price_subtotal_incl for cl in matched_cart_lines)
                        if not applicable_total:
                            applicable_total = sum(cl.price_unit * cl.qty for cl in matched_cart_lines)

                        if applicable_total:
                            discount_amount = abs(rl.price_subtotal_incl)
                            rl_percentage = (discount_amount / applicable_total) * 100.0
                            for cl in matched_cart_lines:
                                cl.write({
                                    'discount': cl.discount + rl_percentage - (cl.discount * rl_percentage / 100.0),
                                    'discount_reward': reward.id,
                                    'reward_id': reward.id,
                                })

                            lines_to_unlink |= rl

            if lines_to_unlink:
                lines_to_unlink.unlink()

            # 2. Recalculate and synchronize (as original recalculate method did)
            if not reward_lines and was_posted:
                invoice.line_ids.remove_move_reconcile()
                invoice.with_context(skip_invoice_sync=True, check_move_validity=False).button_draft()

            order._recalculate_order_lines_and_totals()
            if invoice:
                order._synchronize_invoice(invoice, was_posted=was_posted)

        return True


class UsedCredits(models.Model):
    _name = 'used.credits'
    _description = "used credits"

    used_credit_id = fields.Many2one('pos.order', string="Used Credit")
    credit_id = fields.Integer("Credit Id")
    partner_credit_id = fields.Many2one('res.partner.credit.note', "Voucher No.",
                                        compute="_compute_partner_credit_id")
    amount = fields.Float('Used Amount')

    def _compute_partner_credit_id(self):
        for rec in self:
            partner_credit_id = False
            if rec.credit_id:
                partner_credit_id = rec.credit_id
            rec.partner_credit_id = partner_credit_id


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    nhcl_cashier = fields.Char(string="Cashier", related='pos_order_id.employee_id.name', store=True, readonly=True)
    nhcl_counter_id = fields.Many2one(
        'pos.config',
        string='Counter',
        related='session_id.config_id',
        store=True,
        readonly=True
    )
    order_ref_no = fields.Char(string="Bill Ref No", related='pos_order_id.name',
                               store=True, readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', related='pos_order_id.partner_id',
                                  store=True, readonly=True)
    order_total = fields.Float(string="Total", related='pos_order_id.amount_total',
                               store=True, readonly=True)
    order_date = fields.Datetime(string="Date", related='pos_order_id.date_order',  # POS order date
                                 store=True, readonly=True)

    # je_id = fields.Char(string="Old JE", compute="_compute_je_id")
    # new_je = fields.Char(string="New JE", readonly=True)
    #
    # mop_new_je = fields.Char(string="MOP JE", readonly=True)
    #
    # old_payment_method_id = fields.Many2one('pos.payment.method', string="Old Payment Method", readonly=True)
    # is_mop_changed = fields.Boolean(string="Is MOP Changed", compute="_compute_is_mop_changed")
    #
    # @api.depends('payment_method_id', 'old_payment_method_id')
    # def _compute_is_mop_changed(self):
    #     for payment in self:
    #         payment.is_mop_changed = bool(
    #             payment.old_payment_method_id
    #             and payment.payment_method_id != payment.old_payment_method_id
    #         )

    # def write(self, vals):
    #     if 'payment_method_id' in vals:
    #         for payment in self:
    #             if not payment.old_payment_method_id and payment.payment_method_id:
    #                 if payment.payment_method_id.id != vals['payment_method_id']:
    #                     super(PosPayment, payment).write({'old_payment_method_id': payment.payment_method_id.id})
    #     return super().write(vals)
    #
    # @api.depends(
    #     'pos_order_id.session_id',
    #     'payment_method_id',
    #     'payment_method_id.name',
    #     'payment_method_id.journal_id',
    #     'old_payment_method_id',
    # )
    # def _compute_je_id(self):
    #     """
    #     Find the combined session-level payment JE for this payment.
    #     Searches using session_id and journal_id.
    #     """
    #     for payment in self:
    #         je_name = ''
    #         order = payment.pos_order_id
    #         session = order.session_id if order else False
    #         method = payment.old_payment_method_id or payment.payment_method_id
    #
    #         if session and method:
    #             session_name = session.name
    #             method_name = method.name
    #
    #             # Strategy 1: Search by journal_id + session_id / session reference
    #             if method.journal_id:
    #                 domain = [
    #                     ('journal_id', '=', method.journal_id.id),
    #                     ('state', '=', 'posted'),
    #                 ]
    #                 if hasattr(self.env['account.move'], 'pos_session_id'):
    #                     je = self.env['account.move'].search([('pos_session_id', '=', session.id)] + domain, limit=1)
    #                     if je:
    #                         payment.je_id = je.name
    #                         continue
    #
    #                 je = self.env['account.move'].search([('ref', 'ilike', session_name)] + domain, limit=1)
    #                 if je:
    #                     payment.je_id = je.name
    #                     continue
    #
    #             # Strategy 2: Combined JE reference
    #             if method_name:
    #                 combined_domain = [
    #                     ('ref', 'ilike', 'Combine'),
    #                     ('ref', 'ilike', session_name),
    #                     ('ref', 'ilike', method_name),
    #                     ('state', '=', 'posted'),
    #                 ]
    #                 je = self.env['account.move'].search(combined_domain, limit=1)
    #                 if je:
    #                     payment.je_id = je.name
    #                     continue
    #
    #             # Strategy 3: Fallback — search by order name
    #             if order and order.name:
    #                 fallback_domain = [
    #                     ('ref', 'ilike', order.name),
    #                     ('state', '=', 'posted'),
    #                 ]
    #                 if method_name:
    #                     fallback_domain.append(('ref', 'ilike', method_name))
    #                 je = self.env['account.move'].search(fallback_domain, limit=1)
    #                 if je:
    #                     payment.je_id = je.name
    #                     continue
    #
    #         if not je_name and order and order.account_move:
    #             je_name = order.account_move.name
    #
    #         payment.je_id = je_name
    #
    # def _get_je_record(self):
    #     """
    #     Helper: return the actual account.move record for this payment's JE.
    #     Uses session_id and journal_id to locate the entry.
    #     """
    #     self.ensure_one()
    #     order = self.pos_order_id
    #     session = order.session_id if order else False
    #     method = self.old_payment_method_id or self.payment_method_id
    #
    #     if session and method:
    #         session_name = session.name
    #         method_name = method.name
    #
    #         # Strategy 1: Journal + Session ID
    #         if method.journal_id:
    #             domain = [
    #                 ('journal_id', '=', method.journal_id.id),
    #                 ('state', '=', 'posted'),
    #             ]
    #             if hasattr(self.env['account.move'], 'pos_session_id'):
    #                 je = self.env['account.move'].search([('pos_session_id', '=', session.id)] + domain, limit=1)
    #                 if je:
    #                     return je
    #
    #             je = self.env['account.move'].search([('ref', 'ilike', session_name)] + domain, limit=1)
    #             if je:
    #                 return je
    #
    #         # Strategy 2: Combined JE
    #         if method_name:
    #             je = self.env['account.move'].search([
    #                 ('ref', 'ilike', 'Combine'),
    #                 ('ref', 'ilike', session_name),
    #                 ('ref', 'ilike', method_name),
    #                 ('state', '=', 'posted'),
    #             ], limit=1)
    #             if je:
    #                 return je
    #
    #         # Strategy 3: Order-level fallback
    #         if order and order.name:
    #             domain = [
    #                 ('ref', 'ilike', order.name),
    #                 ('state', '=', 'posted'),
    #             ]
    #             if method_name:
    #                 domain.append(('ref', 'ilike', method_name))
    #             je = self.env['account.move'].search(domain, limit=1)
    #             if je:
    #                 return je
    #
    #     if order and order.account_move:
    #         return order.account_move
    #
    #     return self.env['account.move']
    #
    # def action_reverse_je(self):
    #     """
    #     Reverse the payment JE and store the reversal JE name in new_je.
    #     """
    #     for payment in self:
    #         if payment.new_je:
    #             continue
    #
    #         je = payment._get_je_record()
    #
    #         if not je:
    #             raise ValidationError(
    #                 _("No Journal Entry found to reverse for payment method '%s'.")
    #                 % payment.payment_method_id.name
    #             )
    #
    #         if je.state != 'posted':
    #             raise ValidationError(
    #                 _("The Journal Entry %s must be posted before it can be reversed.")
    #                 % je.name
    #             )
    #
    #         # Save original JE details BEFORE reversal
    #         original_je_id = je.id
    #         original_je_name = je.name
    #
    #         # Create reversal wizard
    #         reversal_wizard = self.env['account.move.reversal'].with_context(
    #             active_model='account.move',
    #             active_ids=je.ids,
    #         ).create({
    #             'move_ids': [(6, 0, je.ids)],
    #             'journal_id': je.journal_id.id,
    #             'date': fields.Date.context_today(self),
    #             'reason': _(
    #                 'Reversal of %s payment for order %s'
    #             ) % (
    #                           payment.payment_method_id.name,
    #                           payment.pos_order_id.name,
    #                       ),
    #         })
    #
    #         # Execute reversal
    #         res = reversal_wizard.reverse_moves()
    #
    #         reversal_move = False
    #         # Odoo 17: reverse_moves returns action dict containing created move res_id/domain
    #         if isinstance(res, dict):
    #             if res.get('res_id'):
    #                 reversal_move = self.env['account.move'].browse(res['res_id'])
    #             elif res.get('domain'):
    #                 for dom in res['domain']:
    #                     if isinstance(dom, (list, tuple)) and len(dom) >= 3 and dom[0] == 'id':
    #                         if dom[1] == 'in' and dom[2]:
    #                             reversal_move = self.env['account.move'].browse(dom[2][0])
    #                         elif dom[1] == '=' and dom[2]:
    #                             reversal_move = self.env['account.move'].browse(dom[2])
    #
    #         if not reversal_move or not reversal_move.exists():
    #             # Search by reversed_entry_id
    #             reversal_move = self.env['account.move'].search([
    #                 ('reversed_entry_id', '=', original_je_id),
    #             ], order='id desc', limit=1)
    #
    #         if not reversal_move or not reversal_move.exists():
    #             # Fallback: search by journal and recent creation
    #             ref_search = self.env['account.move'].search([
    #                 ('id', '!=', original_je_id),
    #                 ('journal_id', '=', je.journal_id.id),
    #                 ('state', 'in', ['draft', 'posted']),
    #             ], order='id desc', limit=1)
    #             if ref_search:
    #                 reversal_move = ref_search
    #
    #         if reversal_move and reversal_move.exists():
    #             if reversal_move.state == 'draft':
    #                 reversal_move.action_post()
    #             payment.new_je = reversal_move.name
    #         else:
    #             raise ValidationError(
    #                 _("Reversal was created but could not be found.\n"
    #                   "Please check Journal Entries for a reversal of: %s")
    #                 % original_je_name
    #             )
    #
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'reload',
    #     }
    #
    # def action_post_mop_entry(self):
    #     """
    #     Creates a new Journal Entry for the changed payment method.
    #     Called from the MOP Change tab when user clicks "Post Entry".
    #     """
    #     for payment in self:
    #         if not payment.new_je:
    #             raise ValidationError(
    #                 _("You must first reverse the original Journal Entry from the Payments tab before posting the entry.")
    #             )
    #         if not payment.is_mop_changed:
    #             raise ValidationError(
    #                 _("Please change the Payment Method on the MOP Change tab before posting the entry.")
    #             )
    #         if payment.mop_new_je:
    #             raise ValidationError(
    #                 _("A MOP entry has already been posted for this line: %s")
    #                 % payment.mop_new_je
    #             )
    #
    #         order = payment.pos_order_id
    #         method = payment.payment_method_id
    #         amount = payment.amount
    #
    #         if not method:
    #             raise ValidationError(
    #                 _("Please select a Payment Method before posting the entry.")
    #             )
    #         if not amount or amount <= 0:
    #             raise ValidationError(
    #                 _("Amount must be greater than zero to post an entry.")
    #             )
    #         if not method.journal_id:
    #             raise ValidationError(
    #                 _("Payment method '%s' has no journal configured.")
    #                 % method.name
    #             )
    #
    #         journal = method.journal_id
    #
    #         # DR account: the new payment method's outstanding receipts account
    #         debit_account = (
    #                 journal.company_id.account_journal_payment_credit_account_id
    #                 or journal.default_account_id
    #         )
    #         if not debit_account:
    #             raise ValidationError(
    #                 _("Journal '%s' has no default account set. "
    #                   "Please configure it in Accounting → Journals.")
    #                 % journal.name
    #             )
    #
    #         # CR account: POS receivable account (Debtors PoS — 100410)
    #         pos_receivable_account = (
    #             order.company_id.account_default_pos_receivable_account_id
    #         )
    #         if not pos_receivable_account:
    #             # Fallback: get from partner
    #             pos_receivable_account = (
    #                     order.partner_id.property_account_receivable_id
    #                     or self.env['account.account'].search([
    #                 ('account_type', '=', 'asset_receivable'),
    #                 ('company_id', '=', order.company_id.id),
    #             ], limit=1)
    #             )
    #
    #         if not pos_receivable_account:
    #             raise ValidationError(
    #                 _("Could not determine the POS receivable account. "
    #                   "Please configure it in Accounting settings.")
    #             )
    #
    #         # Build the journal entry
    #         move_vals = {
    #             'journal_id': journal.id,
    #             'date': fields.Date.context_today(self),
    #             'ref': _(
    #                 'MOP Change: %s payment for order %s'
    #             ) % (method.name, order.name),
    #             'line_ids': [
    #                 # Line 1: DR new payment method's account (money coming in)
    #                 (0, 0, {
    #                     'account_id': debit_account.id,
    #                     'name': _(
    #                         'MOP Change - %s - %s'
    #                     ) % (method.name, order.name),
    #                     'debit': amount,
    #                     'credit': 0.0,
    #                     'partner_id': order.partner_id.id if order.partner_id else False,
    #                 }),
    #                 # Line 2: CR POS receivable account (balancing entry)
    #                 (0, 0, {
    #                     'account_id': pos_receivable_account.id,
    #                     'name': _(
    #                         'MOP Change - %s - %s'
    #                     ) % (method.name, order.name),
    #                     'debit': 0.0,
    #                     'credit': amount,
    #                     'partner_id': order.partner_id.id if order.partner_id else False,
    #                 }),
    #             ],
    #         }
    #
    #         new_move = self.env['account.move'].sudo().create(move_vals)
    #         new_move.action_post()
    #
    #         # Store the new JE name on this payment line
    #         payment.mop_new_je = new_move.name
    #
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'reload',
    #     }
