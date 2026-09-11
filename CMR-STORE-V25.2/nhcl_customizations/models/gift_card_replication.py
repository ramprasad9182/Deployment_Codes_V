from odoo import fields, models, api
from collections import defaultdict
import requests
import logging

_logger = logging.getLogger(__name__)


class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    nhcl_used_card = fields.Boolean(string="Used Card", copy=False)


    def update_gift_card(self):
        store_ip = self.env['ir.config_parameter'].sudo().get_param('nhcl_customizations.nhcl_ho_ip')
        store_port = self.env['ir.config_parameter'].sudo().get_param('nhcl_customizations.nhcl_ho_port')
        store_api_key = self.env['ir.config_parameter'].sudo().get_param('nhcl_customizations.nhcl_ho_api_key')
        headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
        gift_card_search = f"http://{store_ip}:{store_port}/api/loyalty.card/search"
        gift_card_domain = [('code', '=', self.code)]
        gift_card_url = f"{gift_card_search}?domain={gift_card_domain}"
        try:
            response = requests.get(gift_card_url, headers=headers_source)
            response.raise_for_status()  # Raises an HTTPError for bad responses

            # Parse the JSON response
            gift_card = response.json()
            gift_card_data = gift_card.get("data", [])
            if gift_card_data:
                program_id = gift_card_data[0]['program_id'][0]['id']
                gift_card_id = gift_card_data[0]['id']
                ho_gift_card_search = f"http://{store_ip}:{store_port}/api/loyalty.program.replication/search"
                ho_gift_card_domain = [('loyalty_program_replication_id', '=', program_id)]
                ho_gift_card_url = f"{ho_gift_card_search}?domain={ho_gift_card_domain}"
                ho_response = requests.get(ho_gift_card_url, headers=headers_source)
                ho_response.raise_for_status()  # Raises an HTTPError for bad responses

                # Parse the JSON response
                ho_gift_card = ho_response.json()
                ho_gift_card_data = ho_gift_card.get("data", [])
                try:
                    if ho_gift_card_data:
                        for ho_gift_card_entry in ho_gift_card_data:
                            record = self.env['rest.api'].search([('api_key','=',ho_gift_card_entry['nhcl_api_key'])])
                            if not record:
                                replication_store_ip = ho_gift_card_entry['nhcl_terminal_ip']
                                replication_store_port = ho_gift_card_entry['nhcl_port_no']
                                replication_store_api = ho_gift_card_entry['nhcl_api_key']
                                replication_headers_source = {'api-key': f"{replication_store_api}", 'Content-Type': 'application/json'}
                                store_gift_card_search = f"http://{replication_store_ip}:{replication_store_port}/api/loyalty.card/search"
                                store_gift_card_domain = [('code', '=', self.code)]
                                store_gift_card_url = f"{store_gift_card_search}?domain={store_gift_card_domain}"
                                try:
                                    store_response = requests.get(store_gift_card_url, headers=replication_headers_source)
                                    store_response.raise_for_status()  # Raises an HTTPError for bad responses

                                    # Parse the JSON response
                                    replicate_gift_card = store_response.json()
                                    replicate_gift_card_data = replicate_gift_card.get("data", [])
                                    if replicate_gift_card_data:
                                        store_gift_card_id = replicate_gift_card_data[0]['id']
                                        card_list = {
                                            'nhcl_used_card': True,
                                            'points': self.points,
                                        }
                                        up_store_url_data1 = f"http://{replication_store_ip}:{replication_store_port}/api/loyalty.card/{store_gift_card_id}"

                                        # Update the Store Gift Card
                                        update_response = requests.put(up_store_url_data1, headers=replication_headers_source, json=card_list)
                                        update_response.raise_for_status()
                                except requests.exceptions.RequestException as e:
                                    _logger.error(
                                        f"'{self.code}' Failed to update Gift Card '{replication_store_ip}' with partner '{replication_store_port}'. Error: {e}")
                                    logging.error(
                                        f"'{self.code}' Failed to update Gift Card '{replication_store_ip}' with partner '{replication_store_port}'. Error: {e}")
                        ho_card_list = {
                            'nhcl_used_card': True,
                            'points': self.points,
                        }
                        up_ho_url_data = f"http://{store_ip}:{store_port}/api/loyalty.card/{gift_card_id}"

                        # Update the HO Gift Card
                        ho_update_response = requests.put(up_ho_url_data, headers=headers_source,
                                                       json=ho_card_list)
                        ho_update_response.raise_for_status()

                except requests.exceptions.RequestException as e:
                    _logger.error(
                        f"'{self.code}' Failed to update Gift Card '{store_ip}' with partner '{store_port}'. Error: {e}")
                    logging.error(
                        f"'{self.code}' Failed to update Gift Card '{store_ip}' with partner '{store_port}'. Error: {e}")
        except requests.exceptions.RequestException as e:
            _logger.error(
                f"'{self.code}' Failed to connect Gift Card '{store_ip}' with partner '{store_port}'. Error: {e}")
            logging.error(
                f"'{self.code}' Failed to connect Gift Card '{store_ip}' with partner '{store_port}'. Error: {e}")


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_pos_order_used = fields.Boolean(string="Is Used", default=False, copy=False)
    is_cash_register_used = fields.Boolean(string="Is Cash Used", default=False, copy=False)
    is_cash_only = fields.Boolean(
        string="Cash Only Order",
        compute="_compute_is_cash_only",
        store=True
    )

    @api.depends('payment_ids', 'payment_ids.payment_method_id')
    def _compute_is_cash_only(self):
        for order in self:
            # No payments → not valid
            if not order.payment_ids:
                order.is_cash_only = False
                continue
            # Remove zero or negative payments
            valid_payments = order.payment_ids.filtered(lambda p: p.amount > 0)
            # If no positive payments → invalid
            if not valid_payments:
                order.is_cash_only = False
                continue
            # Check if any non-cash payment exists
            non_cash = valid_payments.filtered(lambda p: p.payment_method_id.name != 'Cash')
            order.is_cash_only = not bool(non_cash)

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
                coupon.update_gift_card()
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

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_pos_order_used_line = fields.Boolean(string="Is Used", default=False, copy=False)