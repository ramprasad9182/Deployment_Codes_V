# -*- coding: utf-8 -*-
from odoo import fields, models, _
from datetime import datetime


class KsRecentActivityLine(models.Model):
    _name = 'recent.activity'
    _description = 'Users Login/Logout Activity'

    ks_login_date = fields.Datetime('Login Date')
    ks_logout_date = fields.Datetime('Logout Date')
    ks_duration = fields.Char('Duration')
    ks_user_id = fields.Many2one('res.users', string='Users')
    ks_status = fields.Selection([('active', 'Active'), ('close', 'Closed')], string='Status')
    ks_session_id = fields.Char(string='Session Id')

    def ks_action_logout(self):
        """Admin can Logout to any user and evaluate time that how much time the user is activated."""
        for rec in self:
            rec.ks_status = 'close'
            rec.ks_logout_date = datetime.now()
            duration = datetime.now() - rec.ks_login_date
            total_second = duration.seconds
            minute = total_second / 60
            hour = total_second > 3600
            day = duration.days
            if minute and not hour:
                rec.ks_duration = str(int(minute)) + ' Minute'
            if hour and not day:
                hour = total_second / 3600
                minute = (total_second - int(hour) * 3600) / 60
                rec.ks_duration = str(int(hour)) + ' Hour ' + str(int(minute)) + ' Minute'
            if day:
                hour = total_second
                if hour > 3600:
                    hour = hour / 3600
                    minutes = (total_second - (int(hour) * 3600)) / 60
                else:
                    hour = 0
                    minutes = hour / 60
                rec.ks_duration = str(day) + ' Day ' + str(int(hour)) + ' Hour ' + str(int(minutes)) + ' Minute'
