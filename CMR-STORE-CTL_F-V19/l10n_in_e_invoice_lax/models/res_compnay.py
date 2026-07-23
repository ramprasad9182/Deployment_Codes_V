# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Laxicon Solution (<http://www.laxicon.in>).
#
#    For Module Support : info@laxicon.in
#
##############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import requests
import socket
import datetime
import pytz


class Respartner(models.Model):
    _inherit = "res.company"

    e_inv_environment = fields.Selection([('sandbox', 'Sandbox'), ('production', 'Production')], string=" E-invoice Environment", default="sandbox")

    e_inv_api_token = fields.Char("Token")
    e_inv_api_url = fields.Char("API Url")
    e_inv_username = fields.Char(string="UserName")
    e_inv_password = fields.Char(string="Password")
    e_inv_client_id = fields.Char(string="Client Id")
    e_inv_client_secret = fields.Char(string="Client Secret")
    e_inv_sek = fields.Char(string="Sek", readonly=True)
    e_inv_clientId = fields.Char(string="ClientID", readonly=True)
    e_inv_authtoken = fields.Char(string="AuthToken", readonly=True)
    e_inv_tokenexpiry = fields.Datetime(string="TokenExpiry", readonly=True)
    register_email = fields.Char(string="Register Email")

    @api.onchange('e_inv_environment')
    def onchange_e_inv_environment(self):
        if self.e_inv_environment == 'sandbox':
            self.e_inv_api_url = 'https://einvoice.laxicon.in/sandbox'
            self.e_inv_username = 'laxicon'
            self.e_inv_password = 'laxicon@123'
            self.e_inv_client_id = 'ed04984d-8260-4e6e-91f4-77e054f9a889'
            self.e_inv_client_secret = '365d75ed-50e0-4729-9e48-ef75065dd316'

        elif self.e_inv_environment == 'production':
            self.e_inv_api_url = 'https://einvoice.laxicon.in/production'

    def get_ip_address(self):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

    def get_e_inv_token(self):
        # if self.e_inv_authtoken and self.e_inv_tokenexpiry < datetime.datetime.utcnow():
        self.generate_token_for_e_invoice()
        return self.e_inv_authtoken

    def get_e_invoice_header(self):
        headers = {
            "Content-Type": "application/json",
            'username': self.e_inv_username,
            'password': self.e_inv_password,
            'ip_address': self.get_ip_address(),
            'client_id': self.e_inv_client_id,
            'client_secret': self.e_inv_client_secret,
            'gstin': self.vat and self.vat or '',
            }
        if self.e_inv_environment == 'sandbox':
            headers.update({'gstin': '29AABCT1332L000'})
        return headers

    # def generate_token_for_e_invoice(self):
    #     url = self.e_inv_api_url + '/einvoice/authenticate'
    #     if not self.register_email:
    #         raise UserError("Please set Register Email for %s" % self.name)
    #     url += "?email=%s" % self.register_email
    #     payload = {}
    #     headers = self.get_e_invoice_header()

    #     response = requests.request("GET", url, headers=headers, data=payload)
    #     json_data = response.json()
    #     success_data = json_data.get('data') and json_data.get('data') or False
    #     tz = pytz.timezone("Asia/Kolkata")
    #     if json_data.get('status_cd') == 'Sucess' and success_data:
    #         e_inv_sek = success_data.get('Sek')
    #         e_inv_clientId = success_data.get('ClientId')
    #         e_inv_authtoken = success_data.get('AuthToken')
    #         e_inv_tokenexpiry = success_data.get('TokenExpiry')
    #         local_time = tz.localize(fields.Datetime.to_datetime(e_inv_tokenexpiry))
    #         utc_time = local_time.astimezone(pytz.utc)
    #         data = {
    #             'e_inv_sek': e_inv_sek,
    #             'e_inv_clientId': e_inv_clientId,
    #             'e_inv_authtoken': e_inv_authtoken,
    #             'e_inv_tokenexpiry': fields.Datetime.to_string(utc_time)
    #         }
    #         self.write(data)
    #     elif json_data.get('status_cd') == "0":
    #         raise UserError("%s" % json_data.get('status_desc') )

    def generate_token_for_e_invoice(self):
        if self.e_inv_tokenexpiry and fields.Datetime.now() < self.e_inv_tokenexpiry:
            return  # token still valid
        if not self.register_email:
            raise UserError("Please set Register Email for %s" % self.name)
        url = self.e_inv_api_url + '/einvoice/authenticate'
        headers = self.get_e_invoice_header()

        try:
            response = requests.get(
                url,
                headers=headers,
                params={'email': self.register_email},
                timeout=30
            )
        except requests.exceptions.RequestException as e:
            raise UserError(f"API Connection Error: {str(e)}")

        if response.status_code != 200:
            raise UserError(f"API Error: Status Code {response.status_code}")

        try:
            json_data = response.json()
        except ValueError:
            raise UserError("Invalid response from E-Invoice API (not JSON)")

        success_data = json_data.get('data') or {}

        if json_data.get('status_cd') == 'Success' and success_data:
            tz = pytz.timezone("Asia/Kolkata")

            try:
                local_time = tz.localize(
                    fields.Datetime.to_datetime(success_data.get('TokenExpiry'))
                )
                utc_time = local_time.astimezone(pytz.utc)
            except Exception:
                raise UserError("Invalid Token Expiry format from API")

            self.write({
                'e_inv_sek': success_data.get('Sek'),
                'e_inv_clientId': success_data.get('ClientId'),
                'e_inv_authtoken': success_data.get('AuthToken'),
                'e_inv_tokenexpiry': fields.Datetime.to_string(utc_time)
            })

        else:
            error_msg = json_data.get('status_desc') or "Unknown API Error"
            raise UserError(error_msg)
