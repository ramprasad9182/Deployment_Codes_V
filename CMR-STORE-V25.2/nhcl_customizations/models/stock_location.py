# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    cmr_location_type = fields.Selection([
        ("main_location", "Main Location"),
        ("damage_location", "Damage Location"),
        ("return_location", "Return Location")
    ], string="CMR Location Type")
