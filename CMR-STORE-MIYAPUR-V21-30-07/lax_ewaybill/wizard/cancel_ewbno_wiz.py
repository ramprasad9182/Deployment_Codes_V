# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz
from datetime import datetime
import urllib.parse
from odoo.exceptions import UserError


class CancelIRNWizard(models.TransientModel):
    _name = "cancel.ewbno.wizard"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    cancel_reason = fields.Selection([('1', 'Duplicate'), ('2', 'Order Cancelled'), ('3', 'Data Entry mistake'), ('4', 'Others')], string="Cancellation Reason")
    cancel_remark = fields.Char(string="Cancel Remark")

    def cancel_ewaybill(self):
        auth_url = self.invoice_id.company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/canewb'
        if not self.invoice_id.company_id.e_bill_email:
            raise UserError("Pease set Email for %s" % self.invoice_id.company_id.name)
        auth_url += "?email=%s" % urllib.parse.quote(self.invoice_id.company_id.e_bill_email or '')

        auth_url += "&irp=%s" % 'NIC1'
        headers = self.invoice_id.company_id.sudo().get_e_bill_header()
        data = {
            "ewbNo": int(self.invoice_id.ewb_no),
            "cancelRsnCode": int(self.cancel_reason),
            "cancelRmrk": self.cancel_remark,
            }
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            cancelDate = json_data.get('data').get('cancelDate')
            cancelDate = datetime.strptime(cancelDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(fields.Datetime.to_datetime(cancelDate))
            utc_time = local_time.astimezone(pytz.utc)            
            if cancelDate:
                can_data = {
                    'cancel_reason': self.cancel_reason,
                    'cancel_remark': self.cancel_remark,
                    'cancel_date': fields.Datetime.to_string(utc_time),
                }
                self.invoice_id.write(can_data)                
            msg = "EWB No -> %s Successfully Cancel" % json_data.get('data').get('ewayBillNo')
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
        self.invoice_id.state = 'CNL'