from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PosConfig(models.Model):
    _inherit = 'pos.config'

    counted_amount = fields.Float(
        string='Counted Amount',
        compute='_compute_counted_amount',
        inverse='_inverse_counted_amount',
        digits='Account',
        readonly=False,
        help="Counted cash amount for the active POS session."
    )

    @api.depends('current_session_id', 'current_session_id.counted_amount')
    def _compute_counted_amount(self):
        for config in self:
            config.counted_amount = config.current_session_id.counted_amount if config.current_session_id else 0.0

    def _inverse_counted_amount(self):
        for config in self:
            if config.current_session_id:
                config.current_session_id.counted_amount = config.counted_amount

    def action_bulk_close_sessions(self):
        if not self.env.user.has_group('nhcl_pos_sale.group_pos_bulk_close'):
            raise UserError(_("You do not have permission to execute bulk closing of POS sessions."))
        sessions_to_close = self.mapped('current_session_id').filtered(lambda s: s.state != 'closed')
        if not sessions_to_close:
            raise UserError(_("No open sessions found for the selected Point of Sale counters."))
        sessions_to_close.action_bulk_close_session()
        return True


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_bulk_close_session = fields.Boolean(
        string="POS - Enable Bulk Close Sessions",
        compute='_compute_allow_bulk_close_session',
        inverse='_inverse_allow_bulk_close_session',
        search='_search_allow_bulk_close_session',
        help="Allows user to perform bulk closing of POS sessions."
    )

    def _compute_allow_bulk_close_session(self):
        group = self.env.ref('nhcl_pos_sale.group_pos_bulk_close', raise_if_not_found=False)
        for user in self:
            user.allow_bulk_close_session = group in user.groups_id if group else False

    def _inverse_allow_bulk_close_session(self):
        group = self.env.ref('nhcl_pos_sale.group_pos_bulk_close', raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if user.allow_bulk_close_session:
                user.sudo().write({'groups_id': [(4, group.id)]})
            else:
                user.sudo().write({'groups_id': [(3, group.id)]})

    def _search_allow_bulk_close_session(self, operator, value):
        group = self.env.ref('nhcl_pos_sale.group_pos_bulk_close', raise_if_not_found=False)
        if not group:
            return []
        if (operator in ('=', '==') and value) or (operator in ('!=', '<>') and not value):
            return [('groups_id', 'in', [group.id])]
        else:
            return [('groups_id', 'not in', [group.id])]
