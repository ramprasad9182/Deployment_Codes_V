# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz

class CancelIRNWizard(models.TransientModel):
    _name = "cancel.irn.wizard"
    _description = 'Message'

    invoice_id = fields.Many2one('account.move', string="Invoice", readonly=True)
    cancel_reason = fields.Selection([('1', 'Buyer cancels the order'), ('2', 'There are mistakes in the e-invoice'), ('3', 'Incorrect entries'), ('4', 'Duplicate entries')], string="Cancel IRN Reason")
    cancel_irn_remark = fields.Char(string="Cancel Remark")

    def action_cancel_irn(self):
        irn = self.invoice_id.irn_no
        auth_url = self.invoice_id.company_id.e_inv_api_url + '/einvoice/type/CANCEL/version/V1_03'

        if not self.invoice_id.company_id.register_email:
            raise UserError("Pease set Register Email for %s" % self.invoice_id.company_id.name)
        auth_url += "?email=%s" % self.invoice_id.company_id.register_email
        headers = self.invoice_id.company_id.sudo().get_e_invoice_header()

        headers.update({"auth-token": self.invoice_id.company_id.sudo().get_e_inv_token()})
        data = {
          "Irn": self.invoice_id.irn_no,
          "CnlRsn": self.cancel_reason,
          "CnlRem": self.cancel_irn_remark,
        }
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            CancelDate = json_data.get('data').get('CancelDate')
            local_time = tz.localize(fields.Datetime.to_datetime(CancelDate))
            utc_time = local_time.astimezone(pytz.utc)            
            if CancelDate:
                can_data = {
                    'cancel_reason': self.cancel_reason,
                    'cancel_remark': self.cancel_irn_remark,
                    'cancel_date': fields.Datetime.to_string(utc_time),
                }
                self.invoice_id.write(can_data)                
            msg = "IRN -> %s Successfully cancel" % json_data.get('data').get('Irn')

        elif json_data.get('status_cd') == "0":
            title = "Error"
            for err in json.loads(json_data.get('status_desc')):
                msg += str(err['ErrorMessage'])
                msg += '\n'
            # msg += json_data.get('error').get('message')
 
        view = self.env.ref('l10n_in_e_invoice_lax.message_wizard')
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