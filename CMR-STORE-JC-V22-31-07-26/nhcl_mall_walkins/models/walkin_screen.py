from datetime import datetime, timedelta
from odoo import models, fields, api, _
import calendar
from odoo.exceptions import ValidationError


class WalkinScreen(models.Model):
    _name = 'walkin.screen'
    _description = "Daily Walk-Ins"
    _rec_name = 'doc_number'
    _order = 'id asc'

    store_name = fields.Char(string="Store Name", default="Automatic-Khamaam", readonly=True)
    doc_number = fields.Char(string="Document Number", readonly=True, copy=False)
    creation_date = fields.Datetime(string="Creation Date", default=fields.Datetime.now, readonly=True)
    # date = fields.Date(string="Date")

    month = fields.Selection(
        selection=[('01', 'Jan'), ('02', 'Feb'), ('03', 'Mar'), ('04', 'Apr'),
                   ('05', 'May'), ('06', 'Jun'), ('07', 'Jul'), ('08', 'Aug'),
                   ('09', 'Sep'), ('10', 'Oct'), ('11', 'Nov'), ('12', 'Dec')],
        string="Month", default='04', required=True)

    year_id = fields.Many2one('year.master', required=True)
    date_type = fields.Selection([('day', 'Day'), ('hour', 'Hour')],
                                 string="Slot Type", default='hour', required=True)

    line_ids = fields.One2many('walkin.screen.line', 'walkin_screen_id', string="Slots")

    @api.model
    def default_get(self, fields_list):
        res = super(WalkinScreen, self).default_get(fields_list)
        existing = self.search([], order='id')
        if not existing:
            next_number = 1
        else:
            numbers = [int(rec.doc_number[-3:]) for rec in existing if rec.doc_number and rec.doc_number[-3:].isdigit()]
            next_number = max(numbers) + 1 if numbers else 1
        res['doc_number'] = f'STE{str(next_number).zfill(3)}'
        return res

    @api.constrains('year_id')
    def _check_year_match(self):
        current_year = str(datetime.today().year)
        for rec in self:
            if rec.year_id and rec.year_id.name.strip() != current_year:
                raise ValidationError(
                    f"The selected year ({rec.year_id.name}) must match the current year ({current_year})."
                )

    @api.onchange('month', 'year_id', 'date_type')
    def _onchange_generate_lines(self):
        self.line_ids = [(5, 0, 0)]
        if self.month and self.year_id:
            lines = []
            year = int(self.year_id.name)
            month = int(self.month)
            days_in_month = calendar.monthrange(year, month)[1]

            for day in range(1, days_in_month + 1):
                if self.date_type == 'day':
                    lines.append((0, 0, {
                        'date': f"{year}-{month:02d}-{day:02d}",
                    }))
                elif self.date_type == 'hour':
                    for hour in range(9, 23):  # 9 AM to 10 PM IST
                        # IST naive datetime
                        ist_start = datetime(year, month, day, hour, 0, 0)
                        ist_end = datetime(year, month, day, hour + 1, 0, 0)

                        # Convert to UTC (but keep naive)
                        start_time = ist_start - timedelta(hours=5, minutes=30)
                        end_time = ist_end - timedelta(hours=5, minutes=30)

                        lines.append((0, 0, {
                            'select_date': start_time,
                            'end_time': end_time,
                        }))
            self.line_ids = lines


class WalkinScreenLine(models.Model):
    _name = 'walkin.screen.line'
    _description = "Walk-in Entry Line"

    walkin_screen_id = fields.Many2one('walkin.screen', string="Walkin Screen", ondelete="cascade")
    date = fields.Date(string="Date")
    select_date = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")
    no_of_walkins = fields.Integer(string="Number of Walk-ins")

    date_type = fields.Selection(related='walkin_screen_id.date_type', store=False)

    @api.constrains('select_date', 'walkin_screen_id')
    def _check_unique_select_date(self):
        for line in self:
            if line.select_date:
                # Find other lines with the same select_date under the same walkin_screen
                duplicates = self.search([
                    ('id', '!=', line.id),
                    ('walkin_screen_id', '=', line.walkin_screen_id.id),
                    ('select_date', '=', line.select_date),
                ])
                if duplicates:
                    raise ValidationError(
                        f"Duplicate time slot is not allowed within the same document.")
