# -*- coding: utf-8 -*-
from odoo import fields, models
import json
import requests
import pytz
from datetime import datetime, timedelta
from odoo.exceptions import UserError


class ExtendEwaybill(models.TransientModel):
    _name = "extend.ewaybill"
    _description = 'Message'

    invoice_id = fields.Many2one('eway.bill.details', string="Invoice", readonly=True)
    extn_rsn_code = fields.Selection([
        ('1', 'Natural Calamity'), ('2', 'Law and Order Situation'), ('4', 'Transshipment'), ('5', 'Accident'), ('99', 'Others')],
        string='Reasons for extension of validity')
    extn_remarks = fields.Char(string='Extension Remarks')
    consignment_status = fields.Selection([('M', 'inMovement'), ('T', 'inTransit')],
                                          string='Consignment Status')
    transit_type = fields.Selection([('R', 'Regular'), ('T', 'Transit')],
                                    string='Transit Type')
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street2")
    street3 = fields.Char(string="Street3")

    def extend_ewaybill(self):
        """Extend the validity of an E-Way Bill using MasterGST API"""
        self.ensure_one()
        
        # Va lidate required fields
        if not self.invoice_id.company_id.e_bill_email:
            raise UserError("Please set Email for %s" % self.invoice_id.company_id.name)
        if not self.extn_rsn_code or not self.extn_remarks:
            raise UserError("Extension Reason Code and Remarks are mandatory.")
        if not self.consignment_status:
            raise UserError("Consignment Status is mandatory.")
        if self.consignment_status == 'T' and not (self.transit_type and self.street):
            raise UserError("Transit Type and Street are mandatory for In Transit status.")

        # Validate E-Way Bill expiry time
        expiry_time = self.invoice_id.ewb_valid_till
        if not expiry_time:
            raise UserError("E-Way Bill expiry time is missing.")

        # now = fields.Datetime.now()
        # if expiry_time.tzinfo:
        #     expiry_time = expiry_time.astimezone(pytz.utc).replace(tzinfo=None)
        # hours_diff = (expiry_time - now).total_seconds() / 3600
        # if hours_diff > 8 or hours_diff < -8:
        #     raise UserError("You can only extend the E-Way Bill within 8 hours before or after its expiry.")

        # Construct API URL
        auth_url = self.invoice_id.company_id.e_bill_api_url.rstrip('/') + '/ewaybillapi/v1.03/ewayapi/extendvalidity'
        auth_url += f"?email={self.invoice_id.company_id.e_bill_email}&ip_address=192.168.1.102"  # Replace IP dynamically if needed
    
        # Get headers from company configuration
        headers = self.invoice_id.company_id.sudo().get_e_bill_header()
        headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # Prepare request payload
        company = self.invoice_id.company_id
        data = {
            "ewbNo": int(self.invoice_id.ewb_no),
            "vehicleNo": self.invoice_id.vehical_no or "",
            "fromPlace": company.city or "",
            "fromState": int(company.state_id.l10n_in_tin) if company.state_id.l10n_in_tin else 0,
            "remainingDistance": int(self.invoice_id.distance) if self.invoice_id.distance else 0,
            "transDocNo": self.invoice_id.document_no or "",
            "transDocDate": self.invoice_id.document_date.strftime('%d/%m/%Y') if self.invoice_id.document_date else "",
            "transMode": self.invoice_id.transportation_mode or "",
            "extnRsnCode": int(self.extn_rsn_code),
            "extnRemarks": self.extn_remarks,
            "fromPincode": int(company.zip) if company.zip else 0,
            "consignmentStatus": self.consignment_status
        }

        if self.consignment_status == 'T':
            data.update({
                "transitType": self.transit_type or "",
                "addressLine1": self.street or "",
                "addressLine2": self.street2 or "",
                "addressLine3": self.street3 or ""
            })
      
        response = requests.post(url=auth_url, headers=headers, data=json.dumps(data), timeout=30)
        response.raise_for_status()  # Raise exception for HTTP errors
        json_data = response.json()

        print("E-Way Bill extension response: %s", json_data)