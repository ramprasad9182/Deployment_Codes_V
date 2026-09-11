import requests
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)


class SerialNoPopup(models.TransientModel):
    """Created nhcl.serial.no.popup class to add fields and functions"""
    _name = 'nhcl.serial.no.popup'
    _description = "Serial Number PopUp"

    nhcl_picking_id = fields.Many2one('stock.picking', string='Ref Picking')

    def button_confirm(self):
        if self.nhcl_picking_id:
            self.nhcl_picking_id.is_confirm = True
            # if self.nhcl_picking_id.check_ids:
            #     self.nhcl_picking_id.is_quality_done = True
            return self.nhcl_picking_id.with_context(skip_serial_popup=True,skip_sanity_check=True).button_validate()

