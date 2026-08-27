from odoo import api, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model
    def get_valid_lot_ids(self, lot_ids):
        # for lot in lot_ids:
        #     print("id",lot)
        stock_lots = self.sudo().search([
            ('name', '=', lot_ids)])
        if not stock_lots:
            return ['invalid', lot_ids]
        if stock_lots:
            return ['invalid', stock_lots.id]
        # return True