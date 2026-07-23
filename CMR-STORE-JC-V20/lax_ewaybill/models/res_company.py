from odoo import api,fields,models,_
from odoo.exceptions import UserError
import json
import requests
import socket
import datetime
import pytz

class Respartner(models.Model):
    _inherit="res.company" 
   
    e_bill_api_url = fields.Char("API Url")
    e_bill_username = fields.Char(string="UserName")
    e_bill_password = fields.Char(string="Password")
    e_bill_email = fields.Char(string="Email")
    e_bill_client_id = fields.Char(string="Client Id")
    e_bill_client_secret = fields.Char(string="Client Secret")

    e_bill_sek = fields.Char(string="Sek", readonly=True)
    e_bill_clientId = fields.Char(string="ClientID", readonly=True)
    e_bill_authtoken = fields.Char(string="AuthToken", readonly=True)
    e_bill_tokenexpiry = fields.Datetime(string="TokenExpiry", readonly=True)
    # register_email = fields.Char(string="Register Email")
    e_bill_environment = fields.Selection([('sandbox', 'Sandbox'), ('production', 'Production')], string=" E-Way Bill Environment", default="sandbox")
    e_bill_api_token = fields.Char("Token")

    @api.onchange('e_bill_environment')
    def onchange_e_bill_environment(self):
        if self.e_bill_environment == 'sandbox':
            self.e_bill_api_url = 'https://apisandbox.whitebooks.in'
            self.e_bill_username = 'BVMGSP'
            self.e_bill_password = 'Wbooks@0142'
            self.e_bill_client_id = 'EWBS69862578-27c9-455b-bb13-658a97de5e22'
            self.e_bill_client_secret = 'EWBS420392dc-d878-4ae9-b8b7-c4c2b95f6d70'

        elif self.e_bill_environment == 'production':
            self.e_bill_api_url = 'https://api.whitebooks.in'

    def get_ip_address(self):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

    def get_e_bill_header(self):
        headers = {
            "Content-Type": "application/json",
            # 'email': self.e_bill_email,
            # 'username': self.e_bill_username, 
            # 'password': self.e_bill_password, 
            # 'ip_address': self.get_ip_address(),
            'ip_address': '192.168.1.102', 
            'client_id': self.e_bill_client_id, 
            'client_secret': self.e_bill_client_secret,
            'gstin': self.vat and self.vat or '',
            }
        if self.e_bill_environment == 'sandbox':
            headers.update({'gstin': '29AAGCB1286Q000'})
        return headers

    def generate_token_for_e_bill(self):
        url = self.e_bill_api_url + '/ewaybillapi/v1.03/authenticate'
        if not self.e_bill_email:
            raise UserError("Please set Email for %s" % self.name)
        url += "?email=%s" % self.e_bill_email
        url += "&username=%s" % self.e_bill_username 
        url += "&password=%s" % self.e_bill_password
        payload = {}
        headers = self.get_e_bill_header()
        response = requests.request("GET", url, headers=headers, data=payload)
        if response.status_code != 200:
            raise UserError(
                _("E-Way Bill API error: %s - %s" % (response.status_code, response.text))
            )

        try:
            json_data = response.json()
        except ValueError:
            raise UserError(_("Invalid response from API: %s" % response.text))

        tz = pytz.timezone("Asia/Kolkata")

        if json_data.get('status_cd') == '1':
            # Sandbox: check if 'status' format exists
            if 'status' in json_data and 'authtoken' in json_data:
                e_bill_sek = json_data.get('sek')
                e_bill_authtoken = json_data.get('authtoken')
                e_bill_tokenexpiry = fields.Datetime.now() + timedelta(hours=6)  # sandbox doesn't give TokenExpiry
            else:
                # Production style
                success_data = json_data.get('data') or {}
                e_bill_sek = success_data.get('sek')
                e_bill_authtoken = success_data.get('authtoken')
                e_bill_tokenexpiry = success_data.get('TokenExpiry')

            # convert expiry to UTC safely
            if isinstance(e_bill_tokenexpiry, str):
                local_time = tz.localize(fields.Datetime.to_datetime(e_bill_tokenexpiry))
                utc_time = local_time.astimezone(pytz.utc)
                expiry = fields.Datetime.to_string(utc_time)
            else:
                expiry = fields.Datetime.to_string(e_bill_tokenexpiry)

            data = {
                'e_bill_sek': e_bill_sek,
                'e_bill_authtoken': e_bill_authtoken,
                'e_bill_tokenexpiry': expiry,
            }
            self.write(data)

        elif json_data.get('status_cd') == "0":
            raise UserError("%s" % json_data.get('status_desc'))
        
        
class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('vat')
    def check_vat(self):
        for rec in self:
            if rec.country_id.code == 'IN':
                continue
            super().check_vat()