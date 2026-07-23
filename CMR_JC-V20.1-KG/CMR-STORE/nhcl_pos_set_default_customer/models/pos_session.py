from odoo import models


class PosSession(models.Model):
    """
       Inherit pos session for adding multi barcode products in to session
    """
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        """
            Retrieve a list of Point of Sale (POS) UI models to load,
            including the 'multi.barcode.products' model if not already
            present.
        """
        result = super()._pos_ui_models_to_load()
        new_model = 'pos.contact'
        if new_model not in result:
            result.append(new_model)
        return result






