# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import re
from odoo.exceptions import UserError, ValidationError
UPI_PATTERN=re.compile(r'^[\w.-]+@[\w.-]+$')



class pos_payment_method(models.Model):
	_inherit = 'pos.payment.method'

	upi = fields.Boolean(string='UPI')
	pos_upi_payment_ids = fields.Many2many('pos.upi.payment', string='POS Upi Payments')
	is_credit_settlement = fields.Boolean("Is Credit Settlement")


class POSUPIPayment(models.Model):
	_name = 'pos.upi.payment'
	_description='POS UPI Payment'
	_rec_name="name"
		

	name = fields.Char('name',required=True)
	visible_in_pos = fields.Boolean('Visible on Point of Sale')
	upi_name = fields.Char('UPI Name',required=True)
	upi_vpa = fields.Char('UPI VPA',required=True)
	upi_image = fields.Image('Image', max_width=100, max_height=100)
	pos_config_id = fields.Many2one('pos.config', string='POS Config',required=True)

	@api.constrains('upi_vpa')
	def _check_upi_vpa(self):
		for upi in self:
			if not re.match(UPI_PATTERN, upi.upi_vpa):
				raise ValidationError(_(
					"UPI Is Invalid !!!!"
				))

class PosSession(models.Model):
	_inherit = 'pos.session'

	def _loader_params_pos_payment_method(self):
		result = super()._loader_params_pos_payment_method()
		result['search_params']['fields'].extend(['upi', 'pos_upi_payment_ids','is_credit_settlement'])
		return result
	

		
	def _pos_ui_models_to_load(self):
		result = super()._pos_ui_models_to_load()
		result += [
			'pos.upi.payment',
		]
		return result

	def _loader_params_pos_upi_payment(self):
		return {
			'search_params': {
				'domain': [],
				'fields': [],
			}
		}

	def _get_pos_ui_pos_upi_payment(self, params):
		return self.env['pos.upi.payment'].search_read(**params['search_params'])