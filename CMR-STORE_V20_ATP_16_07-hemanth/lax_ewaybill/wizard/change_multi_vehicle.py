# -*- coding: utf-8 -*-
from odoo import fields, models, _
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class ChangeMultiVehicle(models.TransientModel):
    _name = "change.multi.vehicle"
    _description = 'Message'

    eway_bill_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    vehicle_no = fields.Char(string="New Vehicle No")
    new_document_no = fields.Char(string="New Transportation Document No")
    reason_code = fields.Selection([
       ('1', 'Due to Break Down'),
        ('2', 'Due to Transshipment'),
        ('3', 'Others (Pls. Specify)'),
        ('4', 'First Time'),
    ], string="Reasons for Initiate Multi Vehicle Movement")
    remark = fields.Char(string="Remark")
    line_id = fields.Many2one('eway.vehicle.line', string="Vehicle Line", readonly=True)

    def change_multi_vehicle(self):
        vehicle_line = self.line_id
        ebill = vehicle_line.invoice_id
        company = ebill.company_id

        if not company.e_bill_email:
            raise UserError(_("Please set Email for %s") % company.name)

        auth_url = f"{company.e_bill_api_url}/ewaybillapi/v1.03/ewayapi/updtmulti?email={company.e_bill_email}"
        headers = company.sudo().get_e_bill_header()

        data = {
            "ewbNo": int(ebill.ewb_no),
            "groupNo": int(vehicle_line.group_no),
            "oldvehicleNo": vehicle_line.vehicle_no,
            "newVehicleNo": self.vehicle_no,
            "oldTranNo": ebill.document_no,
            "newTranNo": self.new_document_no,
            "fromPlace": company.city,
            "fromState": int(company.state_id.l10n_in_tin),
            "reasonCode": self.reason_code,
            "reasonRem": self.remark
        }

        response = requests.post(url=auth_url, headers=headers, json=data)

        try:
            json_data = response.json()
        except Exception as e:
            raise UserError("Unable to parse JSON response: %s" % str(e))

        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            updateDate = json_data.get('data').get('vehUpdDate')
            updateDate = datetime.strptime(updateDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(fields.Datetime.to_datetime(updateDate))
            utc_time = local_time.astimezone(pytz.utc)            
            if updateDate:
                updated_data = {
                    'vehicle_no': self.vehicle_no,
                    'vehicle_update_date': fields.Datetime.to_string(utc_time),
                }
                self.line_id.write(updated_data)                
            msg = "Updated Vehical Number -> %s" % self.vehicle_no
        elif json_data.get('status_cd') == "0":
            msg = ""
            error_message = json_data.get('error', {}).get('message', '')
            if error_message:
                try:
                    error_data = json.loads(error_message)
                    error_codes = error_data.get("errorCodes", "")
                    if isinstance(error_codes, str):
                        error_codes = [code.strip() for code in error_codes.split(',') if code.strip()]
                    for code in error_codes:
                        error_rec = self.env['ewaybill.error.code'].search([('code', '=', code)], limit=1)
                        if error_rec:
                            msg += f"{error_rec.name}\n"
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
