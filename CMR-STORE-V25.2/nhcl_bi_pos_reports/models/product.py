# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    custom_pos_categ_ids = fields.Many2many(related='pos_categ_ids', string="Custom Pos Category",
                                            domain="[('id', 'in', custom_pos_categ_ids)]")
    bi_pos_reports_category = fields.Many2one('pos.category', string="POS Category Reports",
                                              domain="[('id', 'in', custom_pos_categ_ids)]")

    @api.onchange('pos_categ_ids')
    def _onchange_pos_categ_ids(self):
        if self.pos_categ_ids:
            self.bi_pos_reports_category = False


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    custom_pos_categ_ids = fields.Many2many(related='pos_categ_ids', string="Custom Pos Category")
    bi_pos_reports_category = fields.Many2one('pos.category', string="POS Category Reports",
                                              compute='_compute_pos_reports_category',
                                              inverse='_set_bi_pos_reports_category',
                                              domain="[('id', 'in', custom_pos_categ_ids)]", )

    def _set_bi_pos_reports_category(self):
        self._set_product_variant_field('bi_pos_reports_category')

    @api.depends('product_variant_ids.bi_pos_reports_category')
    def _compute_pos_reports_category(self):
        self._compute_template_field_from_variant_field('bi_pos_reports_category')

    @api.onchange('pos_categ_ids')
    def _onchange_pos_categ_ids(self):
        if self.pos_categ_ids:
            self.bi_pos_reports_category = False
