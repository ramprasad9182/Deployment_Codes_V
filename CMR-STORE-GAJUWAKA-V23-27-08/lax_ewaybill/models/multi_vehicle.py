from odoo import api,fields,models,_


class EwayVehicleLine(models.Model):
    _name = 'eway.vehicle.line'
    _description = 'EWay Vehicle Line'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice")
    vehicle_no = fields.Char(string="Vehicle No")
    group_no = fields.Char(string="Group No")
    qty = fields.Integer(string="Quantity")
    vehicle_ewb_no = fields.Char("EWB No.", readonly=True, copy=False)
    created_date = fields.Datetime(string="Vehicle Added Date", readonly=True, copy=False)
    vehicle_update_date = fields.Datetime(string="Vehicle Update Date", readonly=True, copy=False)

    def change_multi_vehicle(self):
        self.ensure_one()
        wizard = self.env['change.multi.vehicle'].create({
            'eway_bill_id': self.invoice_id.id,
            'vehicle_no': self.vehicle_no,
            'line_id': self.id,
        })
        return {
            'name': _('Change Multi Vehicle'),
            'type': 'ir.actions.act_window',
            'res_model': 'change.multi.vehicle',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
