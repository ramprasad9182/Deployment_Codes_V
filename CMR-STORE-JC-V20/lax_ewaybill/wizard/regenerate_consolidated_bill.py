# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class RegenerateConsolidated(models.TransientModel):
    _name = "regenerate.consolidated"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    reason_code = fields.Selection([
        ('1', 'Natural Calamity'), ('2', 'Law and Order Situation'), ('4', 'Transshipment'), ('5', 'Accident'), ('99', 'Others')],
                string='Reasons for Regenerate Consolidated')
    remark = fields.Char(string="Regenerate Consolidated Remark")

    def regenerate_consolidated_ewaybill(self):
        company = self.invoice_id.company_id
        auth_url = self.invoice_id.company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/regentripsheet'
        if not self.invoice_id.company_id.e_bill_email:
            raise UserError("Pease set Email for %s" % self.invoice_id.company_id.name)
        auth_url += "?email=%s" % self.invoice_id.company_id.e_bill_email
        print(";::::::::::;;auth_url::::::::::::::",auth_url)
        headers = self.invoice_id.company_id.sudo().get_e_bill_header()
        print(";::::::::::::::;headers::::::::::::::", headers)
        data = {
            "tripSheetNo": 3010009433,
            "vehicleNo": self.invoice_id.vehical_no,
            "fromPlace": company.city,
            "fromState": int(company.state_id.l10n_in_tin),
            "reasonCode": self.reason_code,
            "reasonRem": self.remark,
            "transDocNo": self.invoice_id.document_no,
            "transDocDate": self.invoice_id.document_date.strftime('%d/%m/%Y'),
            "transMode": self.invoice_id.transportation_mode,
            }
        data = json.dumps(data)
        print("sent data>>>>>>>>>>>>>>>::::::::::::::;;", data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        print("sent data>>>>>>>>>>>>>>json_data>::::::::::::::;;", json_data)
        # msg = ""
        # title = ""
        # tz = pytz.timezone("Asia/Kolkata")
        # if json_data.get('status_cd') == "1":
        #     title = json_data.get('status_desc')
        #     cancelDate = json_data.get('data').get('cancelDate')
        #     cancelDate = datetime.strptime(cancelDate, "%d/%m/%Y %I:%M:%S %p")
        #     local_time = tz.localize(fields.Datetime.to_datetime(cancelDate))
        #     utc_time = local_time.astimezone(pytz.utc)            
        #     if cancelDate:
        #         can_data = {
        #             'cancel_reason': self.cancel_reason,
        #             'cancel_remark': self.cancel_remark,
        #             'cancel_date': fields.Datetime.to_string(utc_time),
        #         }
        #         self.invoice_id.write(can_data)                
        #     msg = "EWB No -> %s Successfully Cancel" % json_data.get('data').get('ewayBillNo')
        # elif json_data.get('status_cd') == "0":
            # msg = ""
            # error_message = json_data.get('error', {}).get('message', '')
            # if error_message:
            #     try:
            #         error_data = json.loads(error_message)
            #         error_codes = error_data.get("errorCodes", "")
            #         if isinstance(error_codes, str):
            #             error_codes = [code.strip() for code in error_codes.split(',') if code.strip()]
            #             print(";::::::::::::;;;error_codes::::::::::", error_codes)
            #         for code in error_codes:
            #             error_rec = self.env['ewaybill.error.code'].search([('code', '=', code)], limit=1)
            #             print(";::::::::::::;;;error_rec;::::::::::::::", error_rec)
            #             if error_rec:
            #                 msg += f"{error_rec.name}\n"
            #                 print(';:::::::::::msg::::::::::::::::::::', msg)
            #             else:
            #                 msg += f"Error description not found for code {code}\n"
            #     except Exception as e:
            #         msg += f"Unexpected error format: {error_message}\n"
            #         msg += str(e)
            # raise UserError(msg or "An unknown error occurred.")

        # view = self.env.ref('lax_ewaybill.message_wizard')
        # context = dict(self._context or {})
        # context['message'] = msg
        # return {
        #     'name': title,
        #     'type': 'ir.actions.act_window',
        #     'view_mode': 'form',
        #     'res_model': 'message.wizard',
        #     'views': [(view.id, 'form')],
        #     'view_id': view.id,
        #     'target': 'new',
        #     'context': context,
        # }