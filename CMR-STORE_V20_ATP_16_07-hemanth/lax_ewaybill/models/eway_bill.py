from odoo import api, fields, models, _
import json
from datetime import datetime
import requests
import pytz
from odoo.exceptions import UserError
import qrcode
import base64
from io import BytesIO


class EwayBillDetails(models.Model):
    _name = "eway.bill.details"
    _description = "E-way Bill Details"

    name = fields.Char(string="Name", required=True, default="New", copy=False)
    vendor_id = fields.Many2one("res.partner", string="Vendor")
    bill_date = fields.Date(
        "Bill Date", required=True, index=True, copy=False, default=fields.Datetime.now
    )
    distance = fields.Char(string="Distance")
    transportation_mode = fields.Selection(
        [("1", "Road"), ("2", "Rail"), ("3", "Air"), ("4", "Ship"), ("5", "inTransit")],
        string="Transportation Mode",
    )
    transportation_id = fields.Many2one("res.partner", string="Transportor Name")
    transportation_gst = fields.Char(
        related="transportation_id.vat", string="Transportor GST", copy=False
    )
    document_date = fields.Date(string="Transportation Document Date")
    document_no = fields.Char(string="Transportation Document No")
    vehical_no = fields.Char(string="Vehicle No")
    vehical_type = fields.Selection(
        [("O", "ODC"), ("R", "Regular")], string="Vehicle Type"
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ACT", "Active"),
            ("CNL", "Cancelled"),
            ("DIS", "Discarded"),
        ],
        string="Status",
        default="ACT",
    )
    supply_type = fields.Selection(
        [("O", "Outward"), ("I", "Inward")], string="Supply Type", default="O"
    )
    sub_supply_type = fields.Selection(
        [
            ("1", "Supply"),
            ("2", "Import"),
            ("3", "Export"),
            ("4", "Job Work"),
            ("5", "For Own Use"),
            ("6", "Job Work Returns"),
            ("7", "Sales Return"),
            ("8", "Others"),
            ("9", "SKD/CKD"),
            ("10", "Line Sales"),
            ("11", "Recipient Not Known"),
            ("12", "Exhibition or Fairs"),
        ],
        string="Sub Supply Type",
    )
    doc_type = fields.Selection(
        [
            ("INV", "Tax Invoice"),
            ("BIL", "Bill of Supply"),
            ("BOE", "Bill of Entry"),
            ("CHL", "Delivery Challan"),
            ("OTH", "Others"),
        ],
        string="Document Type",
        default="INV",
    )
    doc_date = fields.Date(string="Document Date", default=fields.Date.today)
    item_ids = fields.One2many("eway.bill.item.line", "eway_bill_id", string="Items")
    transaction_type = fields.Selection(
        [
            ("1", "Regular"),
            ("2", "Bill To - Ship To"),
            ("3", "Bill From - Dispatch From"),
            ("4", "Combination of 2 and 3"),
        ],
        string="Transaction Type",
        default="4",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        index=True,
        default=lambda self: self.env.company.id,
    )
    notes = fields.Html("", copy=False)
    l10n_in_type_id = fields.Many2one(
        "l10n.in.ewaybill.type", "E-waybill Document Type", tracking=True
    )

    sub_total = fields.Float(
        string="Untaxed Amount:", compute="compute_tax_amount", store=True
    )
    total_cgst = fields.Float(string="CGST:", compute="compute_tax_amount", store=True)
    total_sgst = fields.Float(string="SGST:", compute="compute_tax_amount", store=True)
    total_igst = fields.Float(string="IGST:", compute="compute_tax_amount", store=True)
    total_cess = fields.Float(string="CESS:", compute="compute_tax_amount", store=True)
    total_tax = fields.Float(
        string="Total Tax:", compute="compute_tax_amount", store=True
    )
    grand_total = fields.Float(
        string="Total:", compute="compute_tax_amount", store=True
    )

    ewb_no = fields.Char("EWB No.", readonly=True, copy=False)
    ewb_date = fields.Datetime("EWB Dt", readonly=True, copy=False)
    ewb_valid_till = fields.Datetime("EWB Valid Till", readonly=True, copy=False)

    vehi_date = fields.Datetime("Veh Upd Date", readonly=True, copy=False)
    vehi_valid_till = fields.Datetime("Valid Upto", readonly=True, copy=False)

    consol_ewb_no = fields.Char("CEWB No.", readonly=True, copy=False)
    consol_ewb_date = fields.Datetime("CEWB Dt", readonly=True, copy=False)

    cancel_reason = fields.Selection(
        [
            ("1", "Duplicate"),
            ("2", "Order Cancelled"),
            ("3", "Data Entry mistake"),
            ("4", "Others"),
        ],
        string="Cancellation Reason",
        copy=False,
    )
    cancel_remark = fields.Char(string="Cancel Remark", copy=False)
    cancel_date = fields.Datetime(string="Cancel Date Time", copy=False)

    transporter_ewb_no = fields.Char("EWB No.", readonly=True, copy=False)
    transporter_date = fields.Datetime("EWB Dt", readonly=True, copy=False)

    vehicle_ewb_no = fields.Char("EWB No.", readonly=True, copy=False)
    group_no = fields.Char(string="Group No", readonly=True, copy=False)

    created_date = fields.Datetime(string="Created Date", readonly=True, copy=False)

    multi_vehicle_total_qty = fields.Integer(string="Total Multi-Vehicle Quantity")

    vehicle_line_ids = fields.One2many(
        "eway.vehicle.line", "invoice_id", string="Vehicle Lines"
    )
    picking_id = fields.Many2one("stock.picking", string="Stock Picking")
    order_id = fields.Many2one("sale.order", string="Sale Order")
    move_id = fields.Many2one("account.move", string="Invoice")
    qr_code = fields.Binary("QR Code", copy=False)

    def generate_qr_code(self):
        for rec in self:

            qr_data = {
                "ewbNo": rec.ewb_no or "",
                "ewb_date": rec.ewb_date.strftime('%d/%m/%Y %H:%M:%S') if rec.ewb_date else "",
                "valid_till": rec.ewb_valid_till.strftime('%d/%m/%Y %H:%M:%S') if rec.ewb_valid_till else "",
                "gstin": rec.company_id.vat or "",
                "company": rec.company_id.name or "",
            }

            qr_text = json.dumps(qr_data)

            qr = qrcode.make(qr_text)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")

            rec.qr_code = base64.b64encode(buffer.getvalue())

    @api.depends(
        "item_ids.price_subtotal",
        "item_ids.tax_cgst",
        "item_ids.tax_sgst",
        "item_ids.tax_igst",
        "item_ids.tax_cess",
    )
    def compute_tax_amount(self):
        for bill in self:
            subtotal = sum(line.price_subtotal for line in bill.item_ids)
            cgst = sum(line.tax_cgst for line in bill.item_ids)
            sgst = sum(line.tax_sgst for line in bill.item_ids)
            igst = sum(line.tax_igst for line in bill.item_ids)
            cess = sum(line.tax_cess for line in bill.item_ids)
            total_tax = cgst + sgst + igst + cess
            grand_total = subtotal + total_tax

            bill.sub_total = subtotal
            bill.total_cgst = cgst
            bill.total_sgst = sgst
            bill.total_igst = igst
            bill.total_cess = cess
            bill.total_tax = total_tax
            bill.grand_total = grand_total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "eway.bill.details"
                ) or _("New")
        return super(EwayBillDetails, self).create(vals_list)

    def generate_json_data(self):
        self.ensure_one()
        company = self.company_id
        vendor = self.vendor_id

        cgst = sgst = igst = cess = total_value = 0.0
        item_list = []

        for line in self.item_ids:
            price = line.product_qty * line.price_unit
            total_value += price

            cgst_line = sgst_line = igst_line = cess_line = 0.0
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    price,
                    currency=self.env.company.currency_id,
                    quantity=1.0,
                    product=line.product_id,
                )
                for tax_line in taxes.get("taxes", []):
                    tax = self.env["account.tax"].browse(tax_line.get("id"))
                    if not tax or not tax.name:
                        continue
                    name = tax.name.upper()
                    if "CGST" in name:
                        cgst_line += tax_line["amount"]
                    elif "SGST" in name:
                        sgst_line += tax_line["amount"]
                    elif "IGST" in name:
                        igst_line += tax_line["amount"]
                    elif "CESS" in name:
                        cess_line += tax_line["amount"]

            cgst += cgst_line
            sgst += sgst_line
            igst += igst_line
            cess += cess_line

            item_list.append(
                {
                    "productName": line.product_id.name,
                    "productDesc": line.name or line.product_id.name,
                    "hsnCode": int(line.product_id.l10n_in_hsn_code or 0),
                    "quantity": line.product_qty,
                    "qtyUnit": line.product_uom.name or "NOS",
                    "taxableAmount": round(price, 2),
                    "sgstRate": round(sgst_line * 100 / price, 2) if price else 0,
                    "cgstRate": round(cgst_line * 100 / price, 2) if price else 0,
                    "igstRate": round(igst_line * 100 / price, 2) if price else 0,
                    "cessRate": round(cess_line * 100 / price, 2) if price else 0,
                }
            )

        tot_inv_value = total_value + cgst + sgst + igst + cess

        final_data_dict = {
            "supplyType": self.supply_type,
            "subSupplyType": self.sub_supply_type,
            "subSupplyDesc": " ",
            "docType": self.doc_type,
            "docNo": self.name,
            "docDate": self.doc_date.strftime("%d/%m/%Y"),
            "fromGstin": company.vat,
            "fromTrdName": company.name,
            "fromAddr1": company.street,
            "fromAddr2": company.street2,
            "fromPlace": company.city,
            "actFromStateCode": int(company.state_id.l10n_in_tin),
            "fromPincode": int(company.zip),
            "fromStateCode": int(company.state_id.l10n_in_tin),
            "toGstin": vendor.vat,
            "toTrdName": vendor.name,
            "toAddr1": vendor.street,
            "toAddr2": vendor.street2,
            "toPlace": vendor.city,
            "toPincode": int(vendor.zip),
            "actToStateCode": int(vendor.state_id.l10n_in_tin),
            "toStateCode": int(vendor.state_id.l10n_in_tin),
            "transactionType": int(self.transaction_type),
            "dispatchFromGSTIN": company.vat,
            "dispatchFromTradeName": company.name,
            "shipToGSTIN": company.vat,
            "shipToTradeName": vendor.name,
            "shipToGSTIN": "29ALSPR1722R1Z3",
            "totalValue": round(total_value, 2),
            "cgstValue": round(cgst, 2),
            "sgstValue": round(sgst, 2),
            "igstValue": round(igst, 2),
            "cessValue": round(cess, 2),
            "cessNonAdvolValue": 0,
            "totInvValue": round(tot_inv_value, 2),
            "transMode": self.transportation_mode,
            "transDistance": self.distance,
            "transporterName": self.transportation_id.name,
            "transporterId": self.transportation_gst,
            "transDocNo": self.document_no,
            "transDocDate": (
                self.document_date.strftime("%d/%m/%Y") if self.document_date else ""
            ),
            "vehicleNo": self.vehical_no,
            "vehicleType": self.vehical_type,
            "itemList": item_list,
        }
        return final_data_dict

    def generate_eway_bill(self):
        company_id = self.company_id
        auth_url = company_id.e_bill_api_url + "/ewaybillapi/v1.03/ewayapi/genewaybill"
        if not company_id.e_bill_email:
            raise UserError("Please set Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.e_bill_email
        headers = company_id.sudo().get_e_bill_header()
        # headers.update({"auth-token": company_id.sudo().get_e_bill_token()})
        data = self.generate_json_data()
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        if response.status_code == 200:
            json_data = response.json()
            print("sent data>>>>>>>>>>>>>>json_data::::::::::::::;;", json_data)

        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        status_desc = json_data.get("status_desc")
        if json_data.get("status_cd") == "1":
            title = json_data.get("status_desc")
            final_result = json_data.get("data")
            ewayBillNo = final_result.get("ewayBillNo")
            ewayBillDate = final_result.get("ewayBillDate")
            validUpto = final_result.get("validUpto")
            vehUpdDate = datetime.strptime(ewayBillDate, "%d/%m/%Y %I:%M:%S %p")
            validUpto_dt = datetime.strptime(validUpto, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(vehUpdDate)
            utc_time = local_time.astimezone(pytz.utc)
            local_time_valid = tz.localize(validUpto_dt)
            utc_time_valid = local_time_valid.astimezone(pytz.utc)
            # Convert datetime
            ewb_date_str = fields.Datetime.to_string(utc_time)
            valid_till_str = fields.Datetime.to_string(utc_time_valid)

            # QR DATA (string-safe)
            qr_data = {
                "ewbNo": ewayBillNo,
                "ewb_date": ewayBillDate,
                "valid_till": validUpto,
                "gstin": self.company_id.vat or "",
                "company": self.company_id.name or "",
            }

            qr = qrcode.make(json.dumps(qr_data))
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            
            self.write({
                "ewb_no": ewayBillNo,
                "ewb_date": ewb_date_str,
                "ewb_valid_till": valid_till_str,
                "qr_code": base64.b64encode(buffer.getvalue())
            })
            self.env.cr.commit()
            self.generate_qr_code()
            msg = "Your EWB Number => %s" % ewayBillNo
        elif json_data.get("status_cd") == "0":
            if status_desc:
                for err in json.loads(status_desc):
                    msg += str(err["ErrorMessage"])
                    msg += "\n"

    def update_vehicle_no(self):
        if not self.ewb_no:
            raise UserError("Please Generate EWB number")
        wiz_id = self.env["update.vehicle"].create({"eway_bill_id": self.id})
        return {
            "name": _("Update Vehicle"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "update.vehicle",
            "views": [
                (self.env.ref("lax_ewaybill.update_vehicle_wizard").id, "form")
            ],
            "view_id": self.env.ref("lax_ewaybill.update_vehicle_wizard").id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def generate_consolidated_ewaybill(self):
        company_id = self.company_id
        auth_url = company_id.e_bill_api_url + "/ewaybillapi/v1.03/ewayapi/gencewb"
        if not company_id.e_bill_email:
            raise UserError("Please set Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.e_bill_email
        headers = company_id.sudo().get_e_bill_header()
        data = {
            "fromPlace": self.transportation_id.city or "Unknown",
            "fromState": int(self.transportation_id.state_id.l10n_in_tin),
            "vehicleNo": self.vehical_no,
            "transMode": self.transportation_mode or "1",
            "transDocNo": self.document_no,
            "transDocDate": (
                self.document_date.strftime("%d/%m/%Y") if self.document_date else ""
            ),
            "tripSheetEwbBills": [
                {
                    "ewbNo": int(self.ewb_no),
                }
            ],
        }
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()
        msg = ""
        title = ""
        tz = pytz.timezone("Asia/Kolkata")
        status_desc = json_data.get("status_desc")
        if json_data.get("status_cd") == "1":
            title = json_data.get("status_desc")
            final_result = json_data.get("data")
            cEwbNo = final_result.get("cEwbNo")
            cEwbDate = final_result.get("cEwbDate")
            cEwbDate = datetime.strptime(cEwbDate, "%d/%m/%Y %I:%M:%S %p")
            local_time = tz.localize(cEwbDate)
            utc_time = local_time.astimezone(pytz.utc)
            local_time_valid = tz.localize(cEwbDate)
            utc_time_valid = local_time_valid.astimezone(pytz.utc)
            ewb_date_data = {
                "consol_ewb_no": cEwbNo,
                "consol_ewb_date": fields.Datetime.to_string(utc_time),
            }
            self.write(ewb_date_data)
            msg = "Your CEWB Number => %s" % cEwbNo
        elif json_data.get("status_cd") == "0":
            if status_desc:
                for err in json.loads(status_desc):
                    msg += str(err["ErrorMessage"])
                    msg += "\n"

    def cancel_ewbno(self):
        if not self.ewb_no:
            raise UserError("Please Generate EWB number")

        wiz_id = self.env["cancel.ewbno.wizard"].create({"invoice_id": self.id})
        return {
            "name": _("Cancel EWB No"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "cancel.ewbno.wizard",
            "views": [
                (self.env.ref("lax_ewaybill.cancel_irn_wizard").id, "form")
            ],
            "view_id": self.env.ref("lax_ewaybill.cancel_irn_wizard").id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def reject_ewbno(self):
        company_id = self.company_id
        auth_url = company_id.e_bill_api_url + "/ewaybillapi/v1.03/ewayapi/rejewb"
        if not company_id.e_bill_email:
            raise UserError("Please set Email for %s" % company_id.name)
        auth_url += "?email=%s" % company_id.e_bill_email
        headers = company_id.sudo().get_e_bill_header()
        data = {
            "ewbNo": int(self.ewb_no),
        }
        data = json.dumps(data)
        response = requests.post(url=auth_url, headers=headers, data=data)
        json_data = response.json()

    def update_transporter(self):
        wiz_id = self.env["update.transpoter"].create({"invoice_id": self.id})
        return {
            "name": _("Update Transporter"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "update.transpoter",
            "views": [
                (
                    self.env.ref("lax_ewaybill.update_transpoter_wizard").id,
                    "form",
                )
            ],
            "view_id": self.env.ref("lax_ewaybill.update_transpoter_wizard").id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def extend_ewaybill(self):
        wiz_id = self.env["extend.ewaybill"].create({"invoice_id": self.id})
        return {
            "name": _("Extend Validity of E-Way Bill"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "extend.ewaybill",
            "views": [
                (self.env.ref("lax_ewaybill.extend_ewaybill_wizard").id, "form")
            ],
            "view_id": self.env.ref("lax_ewaybill.extend_ewaybill_wizard").id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def regenerate_consolidated_ewaybill(self):
        wiz_id = self.env["regenerate.consolidated"].create({"invoice_id": self.id})
        return {
            "name": _("Regenerate Consolidated E-Way Bill"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "regenerate.consolidated",
            "views": [
                (
                    self.env.ref(
                        "lax_ewaybill.regenerate_consolidated_wizard"
                    ).id,
                    "form",
                )
            ],
            "view_id": self.env.ref(
                "lax_ewaybill.regenerate_consolidated_wizard"
            ).id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def multi_vehicle_movement(self):
        wiz_id = self.env["multi.vehicle.movement"].create({"invoice_id": self.id})
        return {
            "name": _("Initiate Multi Vehicle Movement"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "multi.vehicle.movement",
            "views": [
                (
                    self.env.ref(
                        "lax_ewaybill.multi_vehicle_movement_wizard"
                    ).id,
                    "form",
                )
            ],
            "view_id": self.env.ref(
                "lax_ewaybill.multi_vehicle_movement_wizard"
            ).id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def add_multi_vehicle(self):
        wiz_id = self.env["add.multi.vehicle"].create({"invoice_id": self.id})
        return {
            "name": _("Add Multi Vehicle"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "add.multi.vehicle",
            "views": [
                (
                    self.env.ref("lax_ewaybill.add_multi_vehicle_wizard").id,
                    "form",
                )
            ],
            "view_id": self.env.ref("lax_ewaybill.add_multi_vehicle_wizard").id,
            "target": "new",
            "res_id": wiz_id.id,
        }

    def get_ewaybill(self):
        url = self.company_id.e_bill_api_url + "/ewaybillapi/v1.03/ewayapi/getewaybill"
        if not self.company_id.e_bill_email:
            raise UserError("Please set Email for %s" % self.name)
        url += "?email=%s" % self.company_id.e_bill_email
        url += "&ewbNo=%s" % self.ewb_no
        payload = {}
        headers = self.company_id.get_e_bill_header()
        response = requests.request("GET", url, headers=headers, data=payload)
        json_data = response.json()

    # def get_ewaybill_transporter_by_date(self):
    #     url = self.company_id.e_bill_api_url + '/ewaybillapi/v1.03/ewayapi/getewaybillsfortransporter'
    #     if not self.company_id.e_bill_email:
    #         raise UserError("Please set Email for %s" % self.name)
    #     url += "?email=%s" % self.company_id.e_bill_email
    #     date_obj = self.ewb_date
    #     formatted_date = date_obj.strftime("%d/%m/%Y")
    #     print(";::::::::::::;formatted_date:::::::::::::", formatted_date)
    #     url += "&date=%s" % formatted_date
    #     print(";:::::::::::Get EWay bill for transporter by Date::::::::::::::::", self.ewb_date)
    #     print(";:::::::::::::::::URL::::::::::::::::", url)
    #     payload = {}
    #     headers = self.company_id.get_e_bill_header()
    #     print(";:::::::::::::::::::HEADER:::::::::::",headers)
    #     response = requests.request("GET", url, headers=headers, data=payload)
    #     print(";::::::::::::::;;;response;::::::::::::::::",response)
    #     json_data = response.json()
    #     print("json_data............",json_data)


class EwayBillItemLine(models.Model):
    _name = "eway.bill.item.line"
    _description = "E-way Bill Item Details"

    eway_bill_id = fields.Many2one("eway.bill.details", string="E-way Bill")
    sr_no = fields.Integer(string="Sr No.", compute="compute_sr_no", store=True)
    product_id = fields.Many2one("product.product", string="Product")
    name = fields.Text(string="Description", store=True)
    product_qty = fields.Float(
        string="Quantity", digits="Product Unit of Measure", required=True, store=True
    )

    product_uom = fields.Many2one("uom.uom", string="UOM", related="product_id.uom_id")
    price_unit = fields.Float(
        string="Unit Price", required=True, digits="Product Price", store=True
    )
    price_subtotal = fields.Float(string="Total", compute="get_total")
    company_id = fields.Many2one(
        "res.company",
        related="eway_bill_id.company_id",
        string="Company",
        store=True,
        readonly=True,
    )
    tax_ids = fields.Many2many("account.tax")

    tax_cgst = fields.Float(string="CGST", compute="_compute_taxes", store=True)
    tax_sgst = fields.Float(string="SGST", compute="_compute_taxes", store=True)
    tax_igst = fields.Float(string="IGST", compute="_compute_taxes", store=True)
    tax_cess = fields.Float(string="Cess", compute="_compute_taxes", store=True)

    @api.depends("product_qty", "price_unit", "tax_ids")
    def _compute_taxes(self):
        for line in self:
            price = line.product_qty * line.price_unit
            cgst = sgst = igst = cess = 0.0

            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    price,
                    currency=self.env.company.currency_id,
                    quantity=1.0,
                    product=line.product_id,
                )
                for tax_line in taxes.get("taxes", []):
                    tax_id = tax_line.get("id")
                    if not tax_id:
                        continue
                    tax = self.env["account.tax"].browse(tax_id)
                    if not tax or not tax.name:
                        continue
                    tax_name = tax.name.upper()
                    if "CGST" in tax_name:
                        cgst += tax_line["amount"]
                    elif "SGST" in tax_name:
                        sgst += tax_line["amount"]
                    elif "IGST" in tax_name:
                        igst += tax_line["amount"]
                    elif "CESS" in tax_name:
                        cess += tax_line["amount"]

            line.tax_cgst = cgst
            line.tax_sgst = sgst
            line.tax_igst = igst
            line.tax_cess = cess

    @api.depends("eway_bill_id.item_ids")
    def compute_sr_no(self):
        for order in self.mapped("eway_bill_id"):
            for idx, line in enumerate(order.item_ids, start=1):
                line.sr_no = idx

    @api.onchange("product_id")
    def onchange_product_id(self):
        for res in self:
            res.name = res.product_id.name

    @api.depends("product_qty", "price_unit")
    def get_total(self):
        for rec in self:
            rec.price_subtotal = rec.product_qty * rec.price_unit


class EWayBillType(models.Model):
    _name = "l10n.in.ewaybill.type"
    _description = "E-Waybill Document Type"

    name = fields.Char("Type")
    code = fields.Char("Type Code")
    sub_type = fields.Char("Sub-type")
    sub_type_code = fields.Char("Sub-type Code")
    allowed_supply_type = fields.Selection(
        [
            ("both", "Incoming and Outgoing"),
            ("out", "Outgoing"),
            ("in", "Incoming"),
        ],
        string="Allowed for supply type",
    )
    active = fields.Boolean("Active", default=True)

    @api.depends("sub_type")
    def _compute_display_name(self):
        """Show name and sub_type in name"""
        for ewaybill_type in self:
            ewaybill_type.display_name = _(
                "%s (Sub-Type: %s)", ewaybill_type.name, ewaybill_type.sub_type
            )
