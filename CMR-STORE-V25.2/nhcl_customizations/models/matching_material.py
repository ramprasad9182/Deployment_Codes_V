from odoo import models, fields, api, _


class MatchingMaterial(models.Model):
    _name = 'matching.material'
    _description = 'Matching Material Details'
    _order = 'id desc'

    name = fields.Char(string='Name', copy=False, default=lambda self: _('New'))
    date_time_nh = fields.Datetime(string="Date Time", default=fields.Datetime.now, copy=False)
    product_description = fields.Char(string='Product Description', required=True)
    quantity = fields.Float(string='Quantity')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (self.env['ir.sequence'].next_by_code('matching.material'))
        return super().create(vals_list)

    def action_allow_slip(self):
        self.ensure_one()
        return self.env.ref("nhcl_customizations.report_action_allow_slip_mm").report_action(self)