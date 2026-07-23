# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class UpdateTranspoter(models.TransientModel):
    _name = "update.transpoter"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    transportation_id = fields.Many2one('res.partner', string="Transportor Name")
    transporter_gst = fields.Char(string="Transportor ID")

    def update_transporter(self):
        auth_url = self.invoice_id.company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/updatetransporter'
        if not self.invoice_id.company_id.e_bill_email:
            raise UserError("Pease set Email for %s" % self.invoice_id.company_id.name)
        auth_url += "?email=%s" % self.invoice_id.company_id.e_bill_email
        print(";::::::::::;;auth_url::::::::::::::",auth_url)
        headers = self.invoice_id.company_id.sudo().get_e_bill_header()
        print(";::::::::::::::;headers::::::::::::::", headers)
        data = {
            "ewbNo": int(self.invoice_id.ewb_no),
            "transporterId": self.transporter_gst,
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
            final_result = json_data.get('data')
            ewayBillNo = final_result.get('ewayBillNo')
            transporterId = final_result.get('transporterId')
            transUpdateDate = final_result.get('transUpdateDate')
            transUpdateDate = datetime.strptime(transUpdateDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(transUpdateDate)
            utc_time = local_time.astimezone(pytz.utc)         
            if transUpdateDate:
                ewb_date = {
                    'transporter_ewb_no': ewayBillNo,
                    'transportation_gst': transporterId,
                    'transporter_date': fields.Datetime.to_string(utc_time),
                }
                self.invoice_id.write(ewb_date)                
            msg = "Update Transporter => %s  for this Ewb No => %s" % (transporterId, ewayBillNo)
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
