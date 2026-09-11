# store_year.py
from odoo import models, fields

class YearMaster(models.Model):
    _name = 'year.master'
    _description = 'Year Master'

    name = fields.Char(string='Year', required=True)
