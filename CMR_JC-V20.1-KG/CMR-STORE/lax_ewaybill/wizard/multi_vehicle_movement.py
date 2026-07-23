# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class MultiVehicleMovement(models.TransientModel):
    _name = "multi.vehicle.movement"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    reason_code = fields.Selection([
       ('1', 'Due to Break Down'),
        ('2', 'Due to Transshipment'),
        ('3', 'Others (Pls. Specify)'),
        ('4', 'First Time'),
    ], string="Reasons for Initiate Multi Vehicle Movement")
    remark = fields.Char(string="Remark")
    multi_vehicle_total_qty = fields.Integer(string="Total Multi-Vehicle Quantity")

    def multi_vehicle_movement(self):
        company = self.invoice_id.company_id
        vendor = self.invoice_id.vendor_id
        auth_url = self.invoice_id.company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/initmulti'
        if not self.invoice_id.company_id.e_bill_email:
            raise UserError("Pease set Email for %s" % self.invoice_id.company_id.name)
        auth_url += "?email=%s" % self.invoice_id.company_id.e_bill_email
        print(";::::::::::;;auth_url::::::::::::::",auth_url)
        headers = self.invoice_id.company_id.sudo().get_e_bill_header()
        print(";::::::::::::::;headers::::::::::::::", headers)
        if self.invoice_id.group_no:
            raise UserError("Multi Vehicle Movement already initiated for this EWB.")

        if not self.multi_vehicle_total_qty or self.multi_vehicle_total_qty <= 0:
            raise UserError("Please provide a valid total quantity (> 0) for multi vehicle movement.")
        data = {
            "ewbNo": int(self.invoice_id.ewb_no),
            "fromPlace": company.city,
            "fromState": int(company.state_id.l10n_in_tin),
            "toPlace": vendor.city,
            "toState": int(vendor.state_id.l10n_in_tin),
            "reasonCode": self.reason_code,
            "reasonRem": self.remark,
            "totalQuantity": 100,
            "totalQuantity": self.multi_vehicle_total_qty,
            "unitCode": "BOX",
            "transMode": self.invoice_id.transportation_mode,
            }
        data = json.dumps(data)
        print("sent data>>>>>>>>>>>>>>>::::::::::::::;;", data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        print("sent data>>>>>>>>>>>>>>json_data>::::::::::::::;;", json_data)
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            ewbNo = json_data.get('data').get('ewbNo')
            groupNo = json_data.get('data').get('groupNo')
            createdDate = json_data.get('data').get('createdDate')
            createdDate = datetime.strptime(createdDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(fields.Datetime.to_datetime(createdDate))
            utc_time = local_time.astimezone(pytz.utc)            
            if createdDate:
                created_data = {
                    'multi_vehicle_total_qty': self.multi_vehicle_total_qty,
                    'vehicle_ewb_no': ewbNo,
                    'group_no': groupNo,
                    'created_date': fields.Datetime.to_string(utc_time),
                }
                self.invoice_id.write(created_data)                
            msg = "EWB No -> %s Successfully Initiate Multi Vehicle Movement" % json_data.get('data').get('ewbNo')
        elif json_data.get('status_cd') == "0":
            msg = ""
            error_message = json_data.get('error', {}).get('message', '')
            if error_message:
                try:
                    error_data = json.loads(error_message)
                    error_codes = error_data.get("errorCodes", "")
                    if isinstance(error_codes, str):
                        error_codes = [code.strip() for code in error_codes.split(',') if code.strip()]
                        print(";::::::::::::;;;error_codes::::::::::", error_codes)
                    for code in error_codes:
                        error_rec = self.env['ewaybill.error.code'].search([('code', '=', code)], limit=1)
                        print(";::::::::::::;;;error_rec;::::::::::::::", error_rec)
                        if error_rec:
                            msg += f"{error_rec.name}\n"
                            print(';:::::::::::msg::::::::::::::::::::', msg)
                        else:
                            msg += f"Error description not found for code {code}\n"
                except Exception as e:
                    msg += f"Unexpected error format: {error_message}\n"
                    msg += str(e)
            
            raise UserError(msg or "An unknown error occurred.")
           
        view = self.env.ref('lax_ewaybill.message_wizard')
        context = dict(self._context or {})
        context['message'] = msg
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }
