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


class PosOrderLine(models.Model):
    """ The class PosOrder is used to inherit pos.order.line """
    _inherit = 'pos.order.line'

    employe_no = fields.Char(string="Sale Person")
    badge_id = fields.Char(string="Employee Id")
    employ_id = fields.Many2one("hr.employee", string='Employee Name')
    gdiscount =fields.Float("Global discount")
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
    # STOP

    @api.depends('discount_reward', 'reward_id')
    def _compute_nhcl_reward_id(self):
        for line in self:
            line.nhcl_reward_id = line.discount_reward or (line.reward_id.id if line.reward_id else False)

    @api.depends('gdiscount', 'discount')
    def _compute_total_discount(self):
        for line in self:
            net_amount = line.price_unit * line.qty
            total_discount = (net_amount * (line.gdiscount + line.discount) / 100)
            if not total_discount:
                total_discount = (line.qty * line.nhcl_rs_price) - line.price_subtotal_incl
            if line.nhcl_reward_id or line.discount_reward or line.is_reward_line or line.reward_id:
                if line.nhcl_reward_id.buy_with_reward_price == 'yes':
                    line.total_reward_discount = 0.00
                else:
                    # line.total_reward_discount = total_discount or line.price_subtotal_incl
                    line.total_reward_discount = total_discount
                line.total_discount = 0.00
            else:
                line.total_discount = total_discount
                line.total_reward_discount = 0.00

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for line in records:
            # LOT PRICE LOGIC
            if line.pack_lot_ids:
                lot = self.env['stock.lot'].search([
                    ('name', '=', line.pack_lot_ids[0].lot_name),
                    ('product_id', '=', line.pack_lot_ids[0].product_id.id)
                ], limit=1)

                if lot:
                    if lot.rs_price > 0:
                        if not (line.reward_id.reward_type == 'discount' and line.reward_id.buy_with_reward_price == 'yes'):
                            line.price_unit = lot.rs_price
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

                price_unit = abs(line.price_unit)

                tax_ids = self.env['account.tax'].search([
                    ('min_amount', '<=', price_unit),
                    ('max_amount', '>=', price_unit)
                ])

                for tax in tax_ids:
                    if line.reward_id.reward_product_id:
                        product = line.reward_id.reward_product_id
                        tax_id = product.taxes_id.filtered(lambda x: x.id == tax.id)
                        if tax_id:
                            line.tax_ids = tax_id
                            break

                    elif line.reward_id.discount_max_amount > 0 and line.reward_id.buy_with_reward_price == 'no':
                        line.tax_ids = False

                    if not line.reward_id.reward_product_id:
                        product = line.order_id.lines[:1].product_id
                        tax_id = product.taxes_id.filtered(lambda x: x.id == tax.id)
                        if line.reward_id.program_type != 'gift_card' and tax_id:
                            line.tax_ids = tax_id
                            break

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


class PosOrder(models.Model):
    _inherit = 'pos.order'

    _rec_name = 'pos_reference'

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
            order.amount_reward_discount = sum(order.lines.mapped('total_reward_discount'))
            order.amount_discount = sum(order.lines.mapped('total_discount'))
            lines = order.lines.filtered(lambda line: line.is_fix_discount_line)
            order.amount_discount += -sum(lines.mapped('price_unit'))

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
        new_move = self.env['account.move'].sudo().with_company(self.company_id).with_context(default_move_type=move_vals['move_type']).create(move_vals)
        message = _("This invoice has been created from the point of sale session: %s",
            self._get_html_link())

        new_move.message_post(body=message)
        if self.config_id.cash_rounding:
            with self.env['account.move']._check_balanced({'records': new_move}):
                rounding_applied = float_round(self.amount_paid - self.amount_total,
                                            precision_rounding=new_move.currency_id.rounding)
                # PRANAV customisation start
                if new_move.move_type == 'out_invoice':
                    rounding_applied = new_move.tax_totals.get('rounding_amount', rounding_applied)
                # STOP
                rounding_line = new_move.line_ids.filtered(lambda line: line.display_type == 'rounding')
                if rounding_line and rounding_line.debit > 0:
                    rounding_line_difference = rounding_line.debit + rounding_applied
                elif rounding_line and rounding_line.credit > 0:
                    rounding_line_difference = -rounding_line.credit + rounding_applied
                else:
                    rounding_line_difference = rounding_applied
                if rounding_applied:
                    if rounding_applied > 0.0:
                        account_id = new_move.invoice_cash_rounding_id.loss_account_id.id
                    else:
                        account_id = new_move.invoice_cash_rounding_id.profit_account_id.id
                    if rounding_line:
                        if rounding_line_difference:
                            rounding_line.with_context(skip_invoice_sync=True).write({
                                'debit': rounding_applied < 0.0 and -rounding_applied or 0.0,
                                'credit': rounding_applied > 0.0 and rounding_applied or 0.0,
                                'account_id': account_id,
                                'price_unit': rounding_applied,
                            })
                    else:
                        self.env['account.move.line'].sudo().with_context(skip_invoice_sync=True).create({
                            'balance': -rounding_applied,
                            'quantity': 1.0,
                            'partner_id': new_move.partner_id.id,
                            'move_id': new_move.id,
                            'currency_id': new_move.currency_id.id,
                            'company_id': new_move.company_id.id,
                            'company_currency_id': new_move.company_id.currency_id.id,
                            'display_type': 'rounding',
                            'sequence': 9999,
                            'name': self.config_id.rounding_method.name,
                            'account_id': account_id,
                        })
                else:
                    if rounding_line:
                        rounding_line.with_context(skip_invoice_sync=True).unlink()
                if rounding_line_difference:
                    existing_terms_line = new_move.line_ids.filtered(
                        lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
                    existing_terms_line_new_val = float_round(
                        existing_terms_line.balance + rounding_line_difference,
                        precision_rounding=new_move.currency_id.rounding)
                    existing_terms_line.with_context(skip_invoice_sync=True).balance = existing_terms_line_new_val
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
            print("1",gift_card)
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
                customer_domain = [('name', '=', partner.name),('phone', '=', partner.phone)]
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
                    exiting_vocher = partner.credit_note_ids.filtered(lambda x:x.voucher_number == each['voucher_number'])
                    if not exiting_vocher:
                        partner.credit_note_ids.create({
                            'voucher_number': each['voucher_number'],
                            'pos_bill_number': each['pos_bill_number'],
                            'pos_bill_date': each['pos_bill_date'],
                            'total_amount': each['total_amount'],
                            'deducted_amount': each['deducted_amount'],
                            'partner_id': partner.id,
                        })
                    print("customer_credit_notes_data",each['voucher_number'])
            except Exception as e:
                msg = f"Unexpected error while processing {self.name}: {e}"
                ho_id.create_cmr_transaction_server_replication_log("failure", msg)



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

    nhcl_cashier = fields.Char(string="Cashier",related='pos_order_id.employee_id.name', store=True,readonly=True)
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


