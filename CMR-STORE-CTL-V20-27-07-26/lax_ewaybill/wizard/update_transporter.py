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
            status_desc = json_data.get('status_desc')
            msg = self.invoice_id.company_id.parse_ewaybill_error(status_desc)


        view = self.env.ref('lax_ewaybill.message_wizard')
        context = dict(self._context or {})
        context['message'] = msg
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard.ewaybill',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }
