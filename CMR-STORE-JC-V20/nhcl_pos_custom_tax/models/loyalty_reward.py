import re

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    ref_loyalty_rule_id = fields.Many2one('loyalty.rule',string='Loyalty Rule')

    reward_type =fields.Selection(selection_add=[

        ('discount_on_product', 'Discounted Product')],ondelete={'discount_on_product': 'cascade'})

    discount_product_id = fields.Many2one('product.product',string="Discount On Product")
    cmr_discount_product_ids = fields.Many2many(
        'product.product',
        'loyalty_reward_cmr_product_rel',  # ✅ different table
        'reward_id',
        'product_id',
        string="CMR Discount on Products"
    )

    product_price = fields.Float('Price')
    buy_with_reward_price = fields.Selection([('no', 'No'), ('yes', 'Yes')], string="Buy With Reward Price",
                                             default='no', required=True)
    reward_price = fields.Float('Reward Price')
    is_custom_description = fields.Boolean('Is Custom Description Required')
    buy_product_value = fields.Integer('Buy')

    nhcl_discount_product_category_ids = fields.Many2many('product.category',string="Discount Product Categories", store=True)

    cheapest_qty = fields.Float('Cheapest Quantity', default=1)

    @api.onchange('nhcl_discount_product_category_ids')
    def _onchange_nhcl_categories(self):
        if self.nhcl_discount_product_category_ids:
            self.discount_product_category_id = self.nhcl_discount_product_category_ids[0]
        else:
            self.discount_product_category_id = False



    @api.depends('reward_type', 'reward_product_id', 'discount_mode', 'reward_product_tag_id',

                 'discount', 'currency_id', 'discount_applicability', 'all_discount_product_ids')

    def _compute_description(self):

        for reward in self:

            reward_string = ""
            if reward.is_custom_description:
                reward.description = reward.program_id.name

            elif reward.reward_type == 'discount_on_product':

                products = reward.discount_product_id

                if len(products) == 0:

                    reward_string = _('Discount Product')

                elif len(products) == 1:

                    reward_string = _('Discount Product - %s',

                                      reward.discount_product_id.with_context(display_default_code=False).display_name)

                reward.description = reward_string
            elif reward.buy_with_reward_price == 'yes':

                products = reward.discount_product_ids

                if len(products) == 0:

                    reward_string = _('Reward Discount Product')

                elif len(products) == 1:

                    reward_string = _('Discount Product - %s',

                                      reward.discount_product_ids.with_context(display_default_code=False).display_name)

                reward.description = reward_string
            else:

                super(LoyaltyReward, reward)._compute_description()

    @api.onchange("discount_applicability")
    @api.constrains("discount_applicability")
    def _onchange_discounted_products(self):
        for record in self:
            if record.discount_applicability == 'specific':
                for (i, j) in zip(range(0, len(record.program_id.rule_ids)), range(0, len(record.program_id.reward_ids))):
                    record.program_id.reward_ids[j].discount_product_ids = record.program_id.rule_ids[i].product_ids

    @api.onchange("is_custom_description")
    def _onchange_custom_description(self):
        for rec in self:
            rec._compute_description()


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def action_force_money_mode_on_rules(self):
        for program in self:
            if program.program_type != 'gift_card':
                raise UserError(_("This action is only for gift card programs."))

            if program.rule_ids:
                program.rule_ids.write({
                    'reward_point_mode': 'money',
                    'reward_point_amount': 1,
                })
        return True


_digits = lambda v: (re.sub(r'\D', '', str(v)) or None) if v else None


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains('phone', 'mobile')
    def avoid_duplicate_contact(self):
        for r in self:
            nums = {n for n in (_digits(r.phone), _digits(r.mobile)) if n}
            if not nums:
                continue
            for n in nums:
                existing = self.search(['&', ('id', '!=', r.id), '|',
                                        ('phone', 'ilike', n), ('mobile', 'ilike', n)], limit=1)
                if existing:
                    raise ValidationError(_(
                        "Number %(num)s already used by customer %(name)s."
                    ) % {'num': n, 'name': existing.display_name, 'id': existing.id})
# class LoyaltyRule(models.Model):
#     _inherit = 'loyalty.rule'
#
#     def create_rewards(self):
#         if self.ref_product_ids:
#             vals = {
#                 'discount_product_ids': self.ref_product_ids,
#                 'program_id': self.program_id.id,
#                 'discount': 1
#             }
#             self.env['loyalty.reward'].create(vals)
