# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Laxicon Solution (<http://www.laxicon.in>).
#
#    For Module Support : info@laxicon.in
#
##############################################################################
from odoo import api,fields,models,_
from odoo.exceptions import UserError
import datetime
import json
import requests
import re
import logging
import pytz

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    supply = [('B2B', 'B2B'),
            ('SEZWP', 'SEZWP'),
            ('SEZWOP', 'SEZWOP'),
            ('EXPWP', 'EXPWP'),
            ('EXPWOP', 'EXPWOP'),
            ('DEXP', 'DEXP'),]

    supply_type = fields.Selection(supply, string='Supply Type', default="B2B")
    irn_no = fields.Char("IRN No.", readonly=True, copy=False)
    ack_no = fields.Char("Ack No.", readonly=True, copy=False)
    ack_date = fields.Datetime(string="Ack Dt", readonly=True, copy=False)
    signed_invoice = fields.Text("SignedInvoice", readonly=True, copy=False)

    ewb_no = fields.Char("EWB No.", readonly=True, copy=False)
    ewb_date = fields.Datetime("EWB Dt", readonly=True, copy=False)
    ewb_valid_till = fields.Datetime("EWB Valid Till", readonly=True, copy=False)

    cancel_reason = fields.Selection([('1', 'Buyer cancels the order'), ('2', 'There are mistakes in the e-invoice'), ('3', 'Incorrect entries'), ('4', 'Duplicate entries')], string="Cancel IRN Reason", copy=False)
    cancel_remark = fields.Char(string="Cancel IRN Remark", copy=False)
    cancel_date = fields.Datetime(string="Cancel Date Time", copy=False)

    distance = fields.Integer(string="Distance")
    transportation_mode = fields.Selection([('1', 'Road'), ('2', 'Rail'), ('3', 'Air'), ('4', 'Ship')], string='Transportation Mode')
    transportation_id = fields.Many2one('res.partner', string="Transportor Name")
    transportation_gst = fields.Char(related="transportation_id.vat", string="Transportor GST")
    document_date = fields.Date(string="Transportation Document Date")
    document_no = fields.Char(string="Transportation Document No")
    vehical_no = fields.Char(string="Vehicle No")
    vehical_type = fields.Selection([('O', 'ODC'), ('R', 'Regular')], string='Vehicle Type')

    ship_b_no = fields.Char(string="Ship Bill Number")
    ship_b_dt = fields.Date(string="Ship Bill Date")
    port_id = fields.Many2one('port.code', string="Port Code")            
    ref_claim = fields.Selection([('Y', 'Yes'), ('N', 'No')], string="Refund Claim", default='N')
    is_indian_company = fields.Boolean(compute='_compute_is_indian_company', help="True if the company's country is India")

    def _compute_is_indian_company(self):
        india_id = self.env.ref('base.in').id
        for move in self:
            move.is_indian_company = (move.company_id.country_id.id == india_id if move.company_id.country_id else False)

    def generate_json_data(self):
        final_data_dict = {
           "Version": "1.1",
           "TranDtls": self.TranDtls(),
           "DocDtls": self.DocDtls(),
           "SellerDtls": self.SellerDtls(),
           "BuyerDtls": self.BuyerDtls(),
           'DispDtls': self.DispDtls(),
           'ShipDtls': self.ShipDtls(), #It's mandatory only when ShipDtls address is different from buyer details.
           "ItemList": self.ItemList(),
           "ValDtls": self.ValDtls(),
        }
        if self.partner_id.country_id != self.company_id.country_id:
            final_data_dict.update({'ExpDtls': self.ExpDtls})
        return final_data_dict

    def ExpDtls(self):
        return {
            "ShipBNo": self.ship_b_no or "",
            "ShipBDt": self.ship_b_dt.strftime("%d/%m/%Y") if self.ship_b_dt else "",
            "Port": self.port_id.port_code if self.port_id.port_code else "",
            "RefClm": self.ref_claim or "N",
            "ForCur": self.currency_id.name if self.currency_id else "",
            "CntCode": self.partner_id.country_id.code if self.partner_id.country_id else "",
        }

    def ewaybill_by_irn(self):
        company_id = self.company_id
        auth_url = company_id.e_inv_api_url + '/einvoice/type/GENERATE_EWAYBILL/version/V1_03'
        if not company_id.register_email:
            raise UserError("Please set Register Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.register_email
        headers = company_id.sudo().get_e_invoice_header()
        headers.update({"auth-token": company_id.sudo().get_e_inv_token()})
        data = self.generate_ewaybill_data()
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            final_result = json_data.get('data')
            EwbNo = final_result.get('EwbNo')
            EwbDate = final_result.get('EwbDt')
            EwbValidTill = final_result.get('EwbValidTill')
            local_time = tz.localize(fields.Datetime.to_datetime(EwbDate))
            utc_time = local_time.astimezone(pytz.utc)
            local_time_valid = tz.localize(fields.Datetime.to_datetime(EwbValidTill))
            utc_time_valid = local_time_valid.astimezone(pytz.utc)
            ewb_date_data = {
                'ewb_no': EwbNo,
                'ewb_date': fields.Datetime.to_string(utc_time),
                'ewb_valid_till': fields.Datetime.to_string(utc_time_valid),
            }
            self.write(ewb_date_data)
            msg = "Your EWB Number => %s" % EwbNo
        elif json_data.get('status_cd') == "0":
            title = "Error"
            for err in json.loads(json_data.get('status_desc')):
                msg += str(err['ErrorMessage'])
                msg += '\n'

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

    def generate_ewaybill_data(self):
        if not self.irn_no:
            raise UserError("IRN not generated yet. Please generate IRN first.")
        if not self.distance:
            raise UserError(_("Distance is required"))
        if not self.transportation_mode:
            raise UserError(_("Transportation Mode is required"))
        if not self.transportation_gst:
            raise UserError(_("Transportation GST is required"))
        if not self.transportation_id:
            raise UserError(_("Transportation ID is required"))
        if not self.document_date:
            raise UserError(_("Document Date is required"))
        if not self.document_no:
            raise UserError(_("Document No is required"))
        if not self.vehical_no:
            raise UserError(_("Vehicle No is required"))
        if not self.vehical_type:
            raise UserError(_("Vehicle Type is required"))
        data_dict = {
            "Irn": self.irn_no,
            "Distance": self.distance,
            "TransMode": self.transportation_mode,
            "TransId": self.transportation_gst,
            "TransName": self.transportation_id.name,
            "TransDocDt": self.document_date.strftime("%d/%m/%Y"),
            "TransDocNo": self.document_no,
            "VehNo": self.vehical_no,
            "VehType": self.vehical_type,
            "ExpShipDtls": self.ExpShipDtls(),
            "DispDtls": self.DispDtls(),
        }
        return data_dict

    def EwbDtls(self):
        if not self.distance:
            raise UserError(_("Distance is required"))
        if not self.transportation_mode:
            raise UserError(_("Transportation Mode is required"))
        if not self.transportation_gst:
            raise UserError(_("Transportation GST is required"))
        if not self.transportation_id:
            raise UserError(_("Transportation ID is required"))
        if not self.document_date:
            raise UserError(_("Document Date is required"))
        if not self.document_no:
            raise UserError(_("Document No is required"))
        if not self.vehical_no:
            raise UserError(_("Vehicle No is required"))
        if not self.vehical_type:
            raise UserError(_("Vehicle Type is required"))
        data_dict = {
            "Distance": self.distance,
            "TransMode": self.transportation_mode,
            "TransId": self.transportation_gst,
            "TransName": self.transportation_id.name,
            "TransDocDt": self.document_date.strftime("%d/%m/%Y"),
            "TransDocNo": self.document_no,
            "VehNo": self.vehical_no,
            "VehType": self.vehical_type,
        }
        return data_dict

    def generate_irn_and_ewaybill(self):
        company_id = self.company_id
        auth_url = company_id.e_inv_api_url + '/einvoice/type/GENERATE/version/V1_03'
        if not company_id.register_email:
            raise UserError("Please set Register Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.register_email
        headers = company_id.sudo().get_e_invoice_header()
        headers.update({"auth-token": company_id.sudo().get_e_inv_token()})
        data = self.generate_json_data()
        data.update({'EwbDtls': self.EwbDtls()})
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data) 
        json_data = response.json()
        title, msg = self.get_result_from_response(response)
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
        
    def generate_irn(self):
        company_id = self.company_id
        auth_url = company_id.e_inv_api_url + '/einvoice/type/GENERATE/version/V1_03'
        if not company_id.email:
            raise UserError("Please set Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.email
        headers = company_id.sudo().get_e_invoice_header()
        headers.update({"auth-token": company_id.sudo().get_e_inv_token()})
        data = self.generate_json_data()
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data) 
        json_data = response.json()
        title, msg = self.get_result_from_response(response)
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

    def get_result_from_response(self, response):
        json_data = response.json()
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        if json_data.get('status_cd') == "1":
            title = json_data.get('status_desc')
            final_result = json_data.get('data')
            Irn = final_result.get('Irn')
            AckDate = final_result.get('AckDt')
            local_time = tz.localize(fields.Datetime.to_datetime(AckDate))
            utc_time = local_time.astimezone(pytz.utc)
            irn_data = {
                'irn_no': Irn,
                'ack_no': final_result.get('AckNo'),
                'ack_date': fields.Datetime.to_string(utc_time),
                'signed_invoice': final_result.get('SignedInvoice')
            }
            msg = "Your IRN Number => %s" % Irn
            EwbNo = final_result.get('EwbNo')
            if EwbNo:
                EwbDate = final_result.get('EwbDt')
                EwbValidTill = final_result.get('EwbValidTill')
                local_time = tz.localize(fields.Datetime.to_datetime(EwbDate))
                utc_time = local_time.astimezone(pytz.utc)
                local_time_valid = tz.localize(fields.Datetime.to_datetime(EwbValidTill))
                utc_time_valid = local_time_valid.astimezone(pytz.utc)
                irn_data.update({
                    'ewb_no': EwbNo,
                    'ewb_date': fields.Datetime.to_string(utc_time),
                    'ewb_valid_till': fields.Datetime.to_string(utc_time_valid),
                })
                msg += "\n"
                msg += "Your E-way Bill Number => %s" % EwbNo
            self.write(irn_data)
        elif json_data.get('status_cd') == "0":
            title = "Error"
            for err in json.loads(json_data.get('status_desc')):
                msg += str(err['ErrorMessage'])
                msg += '\n'
        return title, msg

    def cancel_irn(self):
        if self.irn_no and self.ewb_no:
            raise UserError("You can not cancel E-way Bill and E-Invoice.")
        if not self.irn_no:
            raise UserError("Please Generate IRN number")

        wiz_id = self.env['cancel.irn.wizard'].create({'invoice_id': self.id})
        return {
            'name': _('Cancel IRN'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cancel.irn.wizard',
            'views': [(self.env.ref('l10n_in_e_invoice_lax.cancel_irn_wizard').id, 'form')],
            'view_id': self.env.ref('l10n_in_e_invoice_lax.cancel_irn_wizard').id,
            'target': 'new',
            'res_id': wiz_id.id,
        }

    def button_draft(self):
        if self.irn_no and self.cancel_remark:
            raise UserError("IRN already cancelled and you can not reset to draft this invoice.")   
        if self.irn_no:
            raise UserError("Please Cancel E-invoice IRN")
        super(AccountMove, self).button_draft()

    def TranDtls(self):
        return {
            "TaxSch": "GST",
            "SupTyp": self.supply_type and self.supply_type or 'B2B',
            "RegRev": "N",
            # "EcmGstin": '29AABCT1332L000', not reqired in B2B transcation
            "IgstOnIntra": "N"
        }

    def DocDtls(self):
        type = "INV"
        if self.move_type == 'out_refund':
            type = 'CRN'
        elif self.move_type == 'in_refund':
            type = 'DBN'
        return {
            'Typ': type,
            'No': self.name,
            'Dt': self.invoice_date.strftime("%d/%m/%Y")
           }

    def SellerDtls(self):
        company_id = self.company_id
        if not company_id.vat and company_id.e_inv_environment == 'production':
            raise UserError("please Set GSTIN Number for %s " % company_id.name)
        if not self.company_id.phone:
            raise UserError("Please Add Phone Number for %s" % company_id.name)
        if not company_id.email:
            raise UserError("Please Add Email for %s" % company_id.name)
        if not company_id.zip:
            raise UserError("Please Add Zip for %s" % company_id.name)
        if not company_id.city:
            raise UserError("Please Add City for %s" % company_id.name)
        if not company_id.city:
            raise UserError("Please Add City for %s" % company_id.name)
        if not company_id.street or len(company_id.street) <= 3:
            raise UserError("Please Add Proper Addess street for %s" % company_id.name)
        if not company_id.street2 or len(company_id.street2) <= 3:
            raise UserError("Please Add Proper Addess street2 for %s" % company_id.name)
        if not company_id.state_id:
            raise UserError("Please Add State for %s" % company_id.name)
        data = {
            "Gstin": company_id.vat and company_id.vat or '',
            "LglNm": company_id.name,
            "Addr1": company_id.street and company_id.street or '',
            "Addr2": company_id.street2 and company_id.street2 or company_id.street,
            "Loc": company_id.city,
            "Pin": company_id.zip,
            "Stcd": company_id.state_id.l10n_in_tin,
            "Ph": company_id.phone.replace(" ", "").replace("+", "").strip(),
            "Em": company_id.email
        }
        if company_id.e_inv_environment == 'sandbox':
            data.update({"Gstin": "29AABCT1332L000"})
        return data

    def BuyerDtls(self):
        if not self.partner_id.phone:
            raise UserError("Please Add Phone Number for %s" % self.partner_id.name)
        if not self.partner_id.email:
            raise UserError("Please Add Email for %s" % self.partner_id.name)
        if not self.partner_id.zip:
            raise UserError("Please Add Zip for %s" % self.partner_id.name)
        if not self.partner_id.city:
            raise UserError("Please Add City for %s" % self.partner_id.name)
        if not self.partner_id.street or len(self.partner_id.street) <= 3:
            raise UserError("Please Add Proper Addess street for %s" % self.partner_id.name)
        if not self.partner_id.street2 or len(self.partner_id.street2) <= 3:
            raise UserError("Please Add Proper Addess street2 for %s" % self.partner_id.name)
        if not self.partner_id.state_id:
            raise UserError("Please Add State for %s" % self.partner_id.name)

        data = {
            "Gstin": self.partner_id.vat and self.partner_id.vat or False,
            "LglNm": self.partner_id.name,
            "Pos": self.partner_id.state_id.l10n_in_tin,
            "Addr1": self.partner_id.street,
            "Addr2": self.partner_id.street2,
            "Loc": self.partner_id.city,
            "Pin": self.partner_id.zip,
            "Stcd": self.partner_id.state_id.l10n_in_tin,
            "Ph": self.partner_id.phone.replace(" ", "").replace("+", "").strip(),
            "Em": self.partner_id.email,
        }
        return data

    def DispDtls(self):
        return {
            "Nm": self.partner_id.name,
            "Addr1": self.partner_id.street,
            "Addr2": self.partner_id.street2,
            "Loc": self.partner_id.city,
            "Pin": self.partner_id.zip,
            "Stcd": self.partner_id.state_id.l10n_in_tin
        }

    def ExpShipDtls(self):
        return {
            "Addr1": self.partner_id.street,
            "Addr2": self.partner_id.street2,
            "Loc": self.partner_id.city,
            "Pin": self.partner_id.zip,
            "Stcd": self.partner_id.state_id.l10n_in_tin
        }

    # non mandatory
    def ShipDtls(self):
        return {
            "Gstin": self.partner_id.vat and self.partner_id.vat or False,
            "LglNm": self.partner_id.name,
            "TrdNm": self.partner_id.name,
            "Addr1": self.partner_id.street,
            "Addr2": self.partner_id.street2,
            "Loc": self.partner_id.city,
            "Pin": self.partner_id.zip,
            "Stcd": self.partner_id.state_id.l10n_in_tin
        }

    # get all item list in detail
    def ItemList(self):
        ItemList = []
        company_id = self.company_id
        cnt = 0
        for item in self.invoice_line_ids:
            cnt += 1
            gst_rate = 0.0
            for tax in item.tax_ids:
                if tax.tax_group_id.name in ["GST", "IGST", "CGST", "SGST"]:  # Filter GST taxes
                    gst_rate += float(tax.amount)  # Sum up the tax percentage
            tax_detail = item._gsts_for_json_file()
            IsServc = "N"
            if item.product_id.type == 'service':
                IsServc = 'Y'
            item_dict = {
                "SlNo": str(cnt),
                "IsServc": IsServc,
                "HsnCd": str(item.product_id.l10n_in_hsn_code),
                "UnitPrice": item.price_unit,
                "TotAmt": item.price_subtotal,
                "AssAmt": item.price_subtotal,
                "GstRt": gst_rate,
                "TotItemVal": item.price_total,
                "PrdDesc": item.product_id.display_name,
                # "Barcde": item.product_id.barcode and item.product_id.barcode or '',
                "Qty": item.quantity,
                "Unit": item.product_id.uom_id.l10n_in_code and item.product_id.uom_id.l10n_in_code[:3] or "UNT",
                "UnitPrice": item.price_unit,
                "Discount": item.discount,
                "PreTaxVal": item.price_subtotal,
                "IgstAmt": tax_detail.get('iamt', 0),
                "CgstAmt": tax_detail.get('samt', 0),
                "SgstAmt": tax_detail.get('camt', 0),
                "CesRt": tax_detail.get('cess', 0),
                "OthChrg": 0,
            }
            ItemList.append(item_dict)
        return ItemList

    def ValDtls(self):
        amts = {'samt': 0.0, 'camt': 0.0, 'iamt': 0.0, 'cess': 0.0}

        for amt in self.tax_totals.get('groups_by_subtotal').get('Untaxed Amount'):
            if amt.get('tax_group_name') == 'SGST':
                amts['samt'] = amt.get('tax_group_amount')
            elif amt.get('tax_group_name') == 'CGST':
                amts['camt'] = amt.get('tax_group_amount')
            elif amt.get('tax_group_name') == 'IGST':
                amts['iamt'] = amt.get('tax_group_amount')
            elif amt.get('tax_group_name') == 'CESS':
                amts['cess'] = amt.get('tax_group_amount')

        data = {
            'AssVal': self.amount_untaxed,
            'CgstVal': amts.get('camt', 0),
            "SgstVal": amts.get('samt', 0), 
            "IgstVal": amts.get('iamt', 0),
            "CesVal": amts.get('cess', 0),
            "RndOffAmt": 0, 
            "TotInvVal": self.amount_total,
        }
        return data


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _gsts_for_json_file(self):
        taxes = self.tax_ids.json_friendly_compute_all(self.price_unit, self.currency_id.id, self.quantity, self.product_id.id, self.partner_id.id)
        amts = {'samt': 0.0, 'camt': 0.0, 'iamt': 0.0, 'cess': 0.0}
        for tax in taxes.get('taxes', []):
            if 'SGST' in tax['name']:
                amts['samt'] += tax['amount']
            elif 'CGST' in tax['name']:
                amts['camt'] += tax['amount']
            elif 'IGST' in tax['name']:
                amts['iamt'] += tax['amount']
            elif 'CESS' in tax['name']:
                amts['cess'] += tax['amount']
        return amts
