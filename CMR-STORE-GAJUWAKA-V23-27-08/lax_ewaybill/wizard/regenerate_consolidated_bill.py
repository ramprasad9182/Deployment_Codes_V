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
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        status_desc = json_data.get('status_desc')
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            final_result = json_data.get('data', {})
            cEwbNo = final_result.get('cEwbNo') if final_result else False
            msg = "Consolidated EWB Regenerated Successfully => %s" % cEwbNo
        elif json_data.get('status_cd') == "0":
            if status_desc:
                msg = company.parse_ewaybill_error(status_desc)

        view = self.env.ref('lax_ewaybill.message_wizard')
        context = dict(self._context or {})
        context['message'] = msg
        return {
            'name': title or "E-Way Bill Message",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard.ewaybill',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }