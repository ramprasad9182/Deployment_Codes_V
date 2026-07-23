# -*- coding: utf-8 -*-
from odoo import fields, models, _
import json
import requests
import pytz
from datetime import datetime
from odoo.exceptions import UserError


class AddMultiVehicle(models.TransientModel):
    _name = "add.multi.vehicle"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    vehicle_no = fields.Char(string="Vehicle No")
    group_no = fields.Char(string="Group No")
    qty = fields.Integer(string="Quantity")

    def add_multi_vehicle(self):
        if not self.qty or self.qty <= 0:
            raise UserError("Quantity must be greater than 0.")

        invoice = self.invoice_id
        company = invoice.company_id

        if not company.e_bill_email:
            raise UserError(_("Please set Email for %s") % company.name)

        added_qty = sum(invoice.vehicle_line_ids.mapped('qty'))
        if added_qty + self.qty > invoice.multi_vehicle_total_qty:
            raise UserError(_(
                "Adding this quantity (%s) will exceed the initiated total (%s). Already added: %s"
            ) % (self.qty, invoice.multi_vehicle_total_qty, added_qty))

        auth_url = f"{company.e_bill_api_url}/ewaybillapi/v1.03/ewayapi/addmulti?email={company.e_bill_email}"
        headers = company.sudo().get_e_bill_header()

        data = {
            "ewbNo": int(invoice.ewb_no),
            "vehicleNo": self.vehicle_no,
            "groupNo": invoice.group_no,
            "transDocNo": invoice.document_no,
            "transDocDate": invoice.document_date.strftime("%d/%m/%Y"),
            "quantity": self.qty,
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
            ewbNo = json_data.get('data').get('ewbNo')
            vehAddedDate = json_data.get('data').get('vehAddedDate')
            vehAddedDate = datetime.strptime(vehAddedDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(fields.Datetime.to_datetime(vehAddedDate))
            utc_time = local_time.astimezone(pytz.utc)            
            if vehAddedDate:
                self.env['eway.vehicle.line'].create({
                    'invoice_id': invoice.id,
                    'vehicle_ewb_no': ewbNo,
                    'vehicle_no': self.vehicle_no,
                    'qty': self.qty,
                    'group_no': invoice.group_no,
                    'created_date': fields.Datetime.to_string(utc_time),
                })
                msg = "EWB No → %s successfully added for Vehicle" % (ewbNo)
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
           