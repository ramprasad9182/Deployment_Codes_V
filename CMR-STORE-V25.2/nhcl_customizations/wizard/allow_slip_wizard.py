from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AllowSlipWizard(models.TransientModel):
    _name = 'allow.slip.wizard'
    _description = "Allow Slip Wizard"

    slip_type = fields.Selection([
        ("exchange", "POS Exchange"),
        ("matching_material", "Matching Material")
    ], string='Slip Type', required=True)

    def button_confirm(self):
        if self.slip_type == 'exchange':
            action = self.env.ref('nhcl_customizations.action_picking_tree_pos_exchange').read()[0]
            # form_view = self.env.ref('nhcl_customizations.your_specific_form_view_id')
        else:
            action = self.env.ref('nhcl_customizations.nhcl_matching_materials_action').read()[0]
            # form_view = self.env.ref('nhcl_customizations.matching_material_form_view')

        # 2. (Optional) Force it to open a specific record and view mode
        action.update({
            # 'views': [(form_view.id, 'form')],
            'view_mode': 'form',
            # 'res_id': self.id,  # Open current record, or pass a different ID
            # 'target': 'current',  # Use 'new' to open it in a pop-up modal
        })

        return action

    def button_confirm(self):
        if self.slip_type == 'exchange':
            search_view_id = self.env.ref('stock.view_picking_internal_search').id
            return {
                'name': 'POS Exchange',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'domain': [('stock_picking_type', '=', 'exchange')],
                'context': {
                    'contact_display': 'partner_address',
                    'default_company_id': self.env.company.id,  # Clean Odoo 17 equivalent for allowed_company_ids[0]
                    'restricted_picking_type_code': 'incoming',
                    'search_default_pos_exchange': 1,
                    'default_stock_picking_type': 'exchange'
                },
                'search_view_id': [search_view_id, 'search'],
                'target': 'current',
            }
        else:
            return {
                'name': 'Matching Material',
                'type': 'ir.actions.act_window',
                'res_model': 'matching.material',
                'view_mode': 'form',
                'target': 'current',
            }