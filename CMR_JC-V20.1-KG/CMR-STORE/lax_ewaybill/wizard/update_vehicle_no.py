# -*- coding: utf-8 -*-
from odoo import fields, models, _
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class UpdateVehicle(models.TransientModel):
    _name = "update.vehicle"
    _description = 'Message'

    eway_bill_id = fields.Many2one('eway.bill.details', string="E-Way Bill No", readonly=True)
    vehicle_no = fields.Char(string="Vehicle No")
    reason_code = fields.Selection([
        ('1', 'Natural Calamity'), ('2', 'Law and Order Situation'), ('4', 'Transshipment'), ('5', 'Accident'), ('99', 'Others')],
        string='Reasons for extension of validity')
    remark = fields.Char(string="Remarks")

    def update_eway_vehical(self):
        company_id = self.eway_bill_id.company_id
        auth_url = company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/vehewb'
        if not company_id.e_bill_email:
            raise UserError("Please set Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.e_bill_email
        print(";::::::::::;;auth_url::::::::::::::",auth_url)
        headers = company_id.sudo().get_e_bill_header()
        print(";::::::::::::::;headers::::::::::::::", headers)
        data = {
            "ewbNo": int(self.eway_bill_id.ewb_no),
            "vehicleNo": self.vehicle_no,
            "fromPlace": self.eway_bill_id.transportation_id.city or "Unknown",
            "fromState": int(self.eway_bill_id.transportation_id.state_id.l10n_in_tin),
            "reasonCode": self.reason_code,
            "reasonRem": self.remark,
            "transDocNo": self.eway_bill_id.document_no,
            "transDocDate": self.eway_bill_id.document_date.strftime("%d/%m/%Y") if self.eway_bill_id.document_date else "",
            "transMode": self.eway_bill_id.transportation_mode or "1"
        }
        data = json.dumps(data)
        print("sent data>>>>>>>>>>>>>>>::::::::::::::;;", data)
        response = requests.post(url=auth_url, headers=headers, data=data) 
        json_data = response.json()
        print("sent data>>>>>>>>>>>>>>json_data>::::::::::::::;;", json_data)
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        status_desc = json_data.get('status_desc')
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            final_result = json_data.get('data')
            vehUpdDate = final_result.get('vehUpdDate')
            validUpto = final_result.get('validUpto')
            vehUpdDate = datetime.strptime(vehUpdDate, "%d/%m/%Y %I:%M:%S %p")
            validUpto = datetime.strptime(validUpto, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(vehUpdDate)
            utc_time = local_time.astimezone(pytz.utc)
            local_time_valid = tz.localize(validUpto)
            utc_time_valid = local_time_valid.astimezone(pytz.utc)
            ewb_date_data = {
                'vehical_no': self.vehicle_no,
                'vehi_date': fields.Datetime.to_string(utc_time),
                'vehi_valid_till': fields.Datetime.to_string(utc_time_valid),
            }
            self.eway_bill_id.write(ewb_date_data)
            msg = "Update Vehicle No => %s" % (self.vehicle_no)
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
