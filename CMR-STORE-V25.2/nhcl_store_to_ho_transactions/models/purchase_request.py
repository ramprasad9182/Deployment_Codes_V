from odoo import models, _, fields, api
import requests
from odoo.exceptions import UserError, ValidationError
from urllib.parse import quote
from odoo.tools.float_utils import float_compare
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    nhcl_replication_status = fields.Boolean('Replication Status', default=False, copy=False)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_warning_message = fields.Char(compute='_compute_update_warning_message')
    nhcl_update_status = fields.Boolean('Update Status', default=False, copy=False)

    invoice_number = fields.Char(string="PO Number")
    upload_type = fields.Selection([
        ('normal', 'Normal'),
        ('pt_upload', 'PT Upload'),
    ], string="Upload Type", default='normal')
    scan_barcode = fields.Char(string="Scan Barcode")
    scan_pt_upload_line_ids = fields.One2many(
        'scan.pt.upload.lines',
        'order_id',
        string="Scan PT Upload Lines"
    )

    @api.onchange('scan_barcode')
    def _onchange_scan_barcode(self):
        if not self.scan_barcode:
            return

        barcode = self.scan_barcode.strip()

        # Find matching PO line
        po_line = self.order_line.filtered(
            lambda l: l.icode_barcode == barcode
        )

        if not po_line:
            raise ValidationError("Barcode not found in Purchase Order lines.")

        po_line = po_line[0]

        # Find already scanned line
        scan_line = self.scan_pt_upload_line_ids.filtered(
            lambda l: l.barcode == barcode
        )

        scanned_qty = scan_line.quantity if scan_line else 0.0

        if scanned_qty >= po_line.product_qty:
            raise ValidationError(
                f"Already scanned full quantity ({po_line.product_qty}) for this barcode."
            )

        if scan_line:
            scan_line.quantity += 1
        else:
            self.scan_pt_upload_line_ids = [(0, 0, {
                'barcode': barcode,
                'quantity': 1
            })]

        # Clear field for next scan
        self.scan_barcode = False

    def _validate_pt_scan_completion(self):
        self.ensure_one()

        if not self.order_line:
            raise ValidationError("Add atleast one line")


        incomplete_lines = []

        for line in self.order_line:
            barcode = line.icode_barcode or "No Barcode"
            ordered_qty = line.product_qty

            scan_line = self.scan_pt_upload_line_ids.filtered(
                lambda l: l.barcode == line.icode_barcode
            )

            scanned_qty = scan_line.quantity if scan_line else 0.0

            if scanned_qty != ordered_qty:
                incomplete_lines.append(
                    f"{barcode}  -  {ordered_qty}  -  {scanned_qty}"
                )

        if incomplete_lines:
            message = (
                    "Following products are not fully scanned:\n\n"
                    "BARCODE  -  ORDERED QTY  -  SCANNED QTY\n"
                    + "\n".join(incomplete_lines)
            )
            raise ValidationError(message)

    # def send_purchase_request_to_ho(self):
    #     self.ensure_one()
    #
    #     # Apply only for PT upload
    #     if self.upload_type == 'pt_upload':
    #         self._validate_pt_scan_completion()
    #
    #     if not self.order_line:
    #         raise ValidationError("Add atleast one line")
    #
    #     ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
    #     for ho in ho_id:
    #         ho_ip = ho.nhcl_terminal_ip
    #         ho_port = ho.nhcl_port_no
    #         api_key = ho.nhcl_api_key
    #         headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
    #         order_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
    #         company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
    #         company_domain = [('name', '=', self.company_id.name)]
    #         company_url = f"{company_search}?domain={company_domain}"
    #         company_data = requests.get(company_url, headers=headers_source).json()
    #         company_id = company_data.get("data")
    #         order_domain = [('origin', '=', self.name), ('company_id', '=', company_id[0]['id'])]
    #         order_url = f"{order_search}?domain={order_domain}"
    #         order_data = requests.get(order_url, headers=headers_source).json()
    #         order_id = order_data.get("data")
    #         if self.invoice_number:
    #             ho_id = self.env['nhcl.ho.store.master'].search([
    #                 ('nhcl_store_type', '=', 'ho'),
    #                 ('nhcl_active', '=', True)
    #             ], limit=1)
    #
    #             if not ho_id:
    #                 raise UserError(_("No active HO configuration found."))
    #
    #             ho_ip = ho_id.nhcl_terminal_ip
    #             ho_port = ho_id.nhcl_port_no
    #             api_key = ho_id.nhcl_api_key
    #             headers_source = {'api-key': f"{api_key}", 'Content-Type': 'application/json'}
    #
    #             # ✅ Get the main HO company where nhcl_company_bool = True
    #             company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
    #             ho_company_domain = [('nhcl_company_bool', '=', True)]
    #             company_url = f"{company_search}?domain={ho_company_domain}"
    #             company_data = requests.get(company_url, headers=headers_source).json()
    #             company_list = company_data.get("data", [])
    #             if not company_list:
    #                 raise UserError(_("No HO company found in HO DB (nhcl_company_bool=True)."))
    #             ho_company_id = company_list[0]['id']
    #
    #             # ✅ Now search for PO under HO company
    #             ho_po_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
    #             order_domain = [('name', '=', self.invoice_number), ('company_id', '=', ho_company_id)]
    #             order_url = f"{ho_po_search}?domain={order_domain}"
    #             ho_order_data = requests.get(order_url, headers=headers_source).json()
    #             ho_orders = ho_order_data.get("data", [])
    #
    #             if not ho_orders:
    #                 raise UserError(_("HO Purchase Order '%s' not found in HO database.") % self.invoice_number)
    #
    #             ho_order_id = ho_orders[0]['id']
    #
    #             # Continue with product comparison logic as before...
    #
    #             # Step 3: Get HO PO products
    #             # ✅ Get HO PO products
    #             ho_line_url = f"http://{ho_ip}:{ho_port}/api/purchase.order.line/search"
    #             ho_line_domain = [('order_id', '=', ho_order_id)]
    #             ho_line_data = requests.get(f"{ho_line_url}?domain={ho_line_domain}", headers=headers_source).json()
    #             ho_lines = ho_line_data.get("data", [])
    #
    #             # Extract HO product default_codes
    #             # HO product codes from HO API (use default_code)
    #             # HO product codes from HO API
    #             ho_product_codes = []
    #             for line in ho_lines:
    #                 name_field = line.get('name', '')
    #                 if '[' in name_field and ']' in name_field:
    #                     # extract code inside brackets
    #                     code = name_field.split(']')[0].replace('[', '').strip()
    #                     ho_product_codes.append(code)
    #
    #             # Current PO product codes
    #             current_product_codes = [
    #                 line.product_id.default_code for line in self.order_line
    #                 if line.product_id and line.product_id.default_code
    #             ]
    #
    #             # Check if at least one HO product exists in current PO
    #             if not all(code in ho_product_codes for code in current_product_codes):
    #                 extra_codes = [code for code in current_product_codes if code not in ho_product_codes]
    #                 raise ValidationError(_(
    #                     "The following product(s) '%s' from current PO '%s' do not exist in HO PO '%s'."
    #                 ) % (", ".join(extra_codes), self.name, self.invoice_number))
    #         if not order_id:
    #             self.ensure_one()
    #             partner_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
    #             partner_domain = [('name', 'ilike', self.partner_id.name.strip())]
    #             encoded_domain = quote(str(partner_domain))
    #             partner_url = f"{partner_search}?domain={encoded_domain}"
    #             partner_data = requests.get(partner_url, headers=headers_source).json()
    #             partner_id = partner_data.get("data", [])
    #             if not partner_id:
    #                 raise UserError(_("Partner '%s' not found in HO.") % self.partner_id.name)
    #             ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
    #             picking_type_domain = [('name', '=', self.picking_type_id.name),
    #                                    ('company_id', '=', company_id[0]['id'])]
    #             picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
    #             picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
    #             picking_type = picking_type_data.get("data")
    #             order_lines = []
    #             for line in self.order_line:
    #                 product_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/search"
    #                 product_domain = [('default_code', '=', line.product_id.default_code),
    #                                   ('nhcl_id', '=', line.product_id.nhcl_id)]
    #                 product_id_url = f"{product_url_data}?domain={product_domain}"
    #                 product_data = requests.get(product_id_url, headers=headers_source).json()
    #                 product_id = product_data.get("data")
    #                 if not product_id:
    #                     raise UserError(_('Product %s not found in HO') % line.product_id.display_name)
    #                 order_lines.append((0, 0, {
    #                     "name": line.name,
    #                     "product_id": product_id[0]['id'],
    #                     "product_qty": line.product_qty,
    #                     "price_unit": line.price_unit,
    #                     "icode_barcode": line.icode_barcode,
    #                     "brand": line.brand,
    #                     "size": line.size,
    #                     "design": line.design,
    #                     "fit": line.fit,
    #                     "colour": line.color,
    #                     "product_excel": line.product_excel,
    #                     "standard_rate": line.standard_rate,
    #                     "mrp": line.mrp,
    #                     "rsp": line.rsp,
    #                     "item_vendor_id": line.item_vendor_id,
    #                     "hsn_sac_code": line.hsn_sac_code,
    #                     "des5": line.des5,
    #                     "des6": line.des6,
    #                 }))
    #             purchase_vals_data = {
    #                 'origin': self.name,
    #                 'partner_id': partner_id[0]['id'],
    #                 'nhcl_po_type': self.nhcl_po_type,
    #                 # 'picking_type_id': picking_type[0]['id'],
    #                 'date_order': self.date_order.strftime("%Y-%m-%d"),
    #                 'company_id': company_id[0]['id'],
    #                 'payment_term_id': self.payment_term_id.id,
    #                 'partner_ref': self.name,
    #                 'currency_id': self.currency_id.id,
    #                 'invoice_number': self.invoice_number,
    #                 'upload_type': self.upload_type,
    #                 'order_line': order_lines,
    #             }
    #             purchase_request_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/create"
    #             purchase_request_data = requests.post(purchase_request_search,
    #                                                   headers=headers_source, json=[purchase_vals_data])
    #             purchase_request_data.raise_for_status()
    #             # Access the JSON content from the response
    #             purchase_request = purchase_request_data.json()
    #             message = purchase_request.get("message", "No message provided")
    #             if purchase_request.get("success") == False:
    #                 _logger.info(
    #                     f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
    #                 logging.error(
    #                     f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error:")
    #                 ho.create_cmr_transaction_server_replication_log('success', message)
    #                 ho.create_cmr_transaction_replication_log(purchase_request['object_name'],
    #                                                           self.id,
    #                                                           200,
    #                                                           'add', 'failure', message)
    #             else:
    #                 _logger.info(
    #                     f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                 logging.info(
    #                     f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                 ho.create_cmr_transaction_server_replication_log('success', message)
    #                 ho.create_cmr_transaction_replication_log(purchase_request['object_name'], self.id,
    #                                                           200,
    #                                                           'add', 'success',
    #                                                           f"Successfully created Delivery Order {self.name}")
    #                 self.nhcl_replication_status = True

    def action_open_upload_wizard(self):
        """Open the wizard for PT upload"""
        return {
            'name': "Upload PT Excel",
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.pt.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    @api.depends('name')
    def _compute_update_warning_message(self):
        self.warning_message = ''
        if self.nhcl_update_status == False:
            self.update_warning_message = 'Update Only Once'
        else:
            self.update_warning_message = 'Successfully Updated!'

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.nhcl_replication_status == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    # def send_purchase_request_to_ho(self):
    #     ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type','=', 'ho'),('nhcl_active','=',True)])
    #     for ho in ho_id:
    #         try:
    #             ho_ip = ho.nhcl_terminal_ip
    #             ho_port = ho.nhcl_port_no
    #             api_key = ho.nhcl_api_key
    #             headers_source = {'api-key':f"{api_key}",'Content_Type':'application/json'}
    #             order_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
    #             order_domain = [('origin', '=', self.name)]
    #             order_url = f"{order_search}?domain={order_domain}"
    #             order_data = requests.get(order_url, headers=headers_source).json()
    #             order_id = order_data.get("data")
    #             if not order_id:
    #                 self.ensure_one()
    #                 company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
    #                 company_domain = [('name', '=', self.company_id.name)]
    #                 company_url = f"{company_search}?domain={company_domain}"
    #                 company_data = requests.get(company_url, headers=headers_source).json()
    #                 company_id = company_data.get("data")
    #                 partner_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
    #                 partner_domain = [('name', '=', self.partner_id.name),('phone','=',self.partner_id.phone)]
    #                 partner_url = f"{partner_search}?domain={partner_domain}"
    #                 partner_data = requests.get(partner_url, headers=headers_source).json()
    #                 partner_id = partner_data.get("data")
    #                 if not partner_id:
    #                     raise UserError(_('Partner not found in HO'))
    #                 ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
    #                 picking_type_domain = [('name', '=', self.picking_type_id.name),('company_id', '=', company_id[0]['id'])]
    #                 picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
    #                 picking_type_data = requests.get(picking_type_url,headers=headers_source).json()
    #                 picking_type = picking_type_data.get("data")
    #                 order_lines = []
    #                 for line in self.order_line:
    #                     product_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/search"
    #                     product_domain = [('name', '=', line.product_id.name), ('nhcl_id', '=', line.product_id.nhcl_id)]
    #                     product_id_url = f"{product_url_data}?domain={product_domain}"
    #                     product_data = requests.get(product_id_url, headers=headers_source).json()
    #                     product_id = product_data.get("data")
    #                     if not product_id:
    #                         raise UserError(_('Product %s not found in HO')%line.product_id.display_name)
    #                     order_lines.append((0, 0, {
    #                         "name": line.name,
    #                         "product_id": product_id[0]['id'],
    #                         "product_qty": line.product_qty,
    #                         "price_unit": line.price_unit,
    #                     }))
    #                 purchase_vals_data = {
    #                     'origin': self.name,
    #                     'partner_id': partner_id[0]['id'],
    #                     'nhcl_po_type': self.nhcl_po_type,
    #                     'picking_type_id': picking_type[0]['id'],
    #                     'date_order': self.date_order.strftime("%Y-%m-%d"),
    #                     'company_id': company_id[0]['id'],
    #                     'payment_term_id': self.payment_term_id.id,
    #                     'partner_ref': self.name,
    #                     'currency_id': self.currency_id.id,
    #                     'order_line': order_lines,
    #                 }
    #                 purchase_request_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/create"
    #                 purchase_request_data = requests.post(purchase_request_search,
    #                                                            headers=headers_source, json=[purchase_vals_data])
    #                 purchase_request_data.raise_for_status()
    #                 # Access the JSON content from the response
    #                 purchase_request = purchase_request_data.json()
    #                 message = purchase_request.get("message", "No message provided")
    #                 print(purchase_request)
    #                 if purchase_request.get("success") == False:
    #                     _logger.info(
    #                     f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
    #                     logging.error(
    #                     f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error:")
    #                     ho.create_cmr_transaction_server_replication_log('success', message)
    #                     ho.create_cmr_transaction_replication_log(purchase_request['object_name'],
    #                                                       self.id,
    #                                                       200,
    #                                                       'add', 'failure', message)
    #                 else:
    #                     _logger.info(
    #                        f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                     logging.info(
    #                          f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                     ho.create_cmr_transaction_server_replication_log('success', message)
    #                     ho.create_cmr_transaction_replication_log(purchase_request['object_name'], self.id,
    #                                                       200,
    #                                                       'add', 'success',
    #                                                       f"Successfully created Delivery Order {self.name}")
    #                     self.nhcl_replication_status = True
    #         except Exception as e:
    #             ho.create_cmr_transaction_server_replication_log("failure", e)

    def send_purchase_request_to_ho(self):
        if not self.order_line:
            raise ValidationError ("Add atleast one line")


        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        for ho in ho_id:
            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            api_key = ho.nhcl_api_key
            headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
            order_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
            company_domain = [('name', '=', self.company_id.name)]
            company_url = f"{company_search}?domain={company_domain}"
            company_data = requests.get(company_url, headers=headers_source).json()
            company_id = company_data.get("data")
            if not company_data.get('success'):
                ho_msg = company_data.get('message') or "HO API validation failed"
                raise ValidationError(f"HO Company: {ho_msg}")
            order_domain = [('origin', '=', self.name), ('company_id', '=', company_id[0]['id'])]
            order_url = f"{order_search}?domain={order_domain}"
            order_data = requests.get(order_url, headers=headers_source).json()
            order_id = order_data.get("data")
            if self.invoice_number:
                ho_id = self.env['nhcl.ho.store.master'].search([
                    ('nhcl_store_type', '=', 'ho'),
                    ('nhcl_active', '=', True)
                ], limit=1)

                if not ho_id:
                    raise UserError(_("No active HO configuration found."))

                ho_ip = ho_id.nhcl_terminal_ip
                ho_port = ho_id.nhcl_port_no
                api_key = ho_id.nhcl_api_key
                headers_source = {'api-key': f"{api_key}", 'Content-Type': 'application/json'}

                # ✅ Get the main HO company where nhcl_company_bool = True
                company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                ho_company_domain = [('nhcl_company_bool', '=', True)]
                company_url = f"{company_search}?domain={ho_company_domain}"
                company_data = requests.get(company_url, headers=headers_source).json()
                company_list = company_data.get("data", [])
                if not company_list:
                    raise UserError(_("No HO company found in HO DB (nhcl_company_bool=True)."))
                ho_company_id = company_list[0]['id']

                # ✅ Now search for PO under HO company
                ho_po_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
                order_domain = [('name', '=', self.invoice_number), ('company_id', '=', ho_company_id)]
                order_url = f"{ho_po_search}?domain={order_domain}"
                ho_order_data = requests.get(order_url, headers=headers_source).json()
                ho_orders = ho_order_data.get("data", [])

                if not ho_orders:
                    raise UserError(_("HO Purchase Order '%s' not found in HO database.") % self.invoice_number)

                ho_order_id = ho_orders[0]['id']

                # Continue with product comparison logic as before...

                # Step 3: Get HO PO products
                # ✅ Get HO PO products
                ho_line_url = f"http://{ho_ip}:{ho_port}/api/purchase.order.line/search"
                ho_line_domain = [('order_id', '=', ho_order_id)]
                ho_line_data = requests.get(f"{ho_line_url}?domain={ho_line_domain}", headers=headers_source).json()
                ho_lines = ho_line_data.get("data", [])

                # Extract HO product default_codes
                # HO product codes from HO API (use default_code)
                # HO product codes (unique)
                ho_product_codes = {
                    line.get('name', '').split(']')[0].replace('[', '').strip()
                    for line in ho_lines
                    if '[' in line.get('name', '') and ']' in line.get('name', '')
                }

                # Current PO product codes (unique)
                current_product_codes = {
                    line.product_id.default_code
                    for line in self.order_line
                    if line.product_id and line.product_id.default_code
                }

                # Find products that are not present in the HO PO
                extra_codes = sorted(current_product_codes - ho_product_codes)

                if extra_codes:
                    raise ValidationError(_(
                        "The following product(s) '%s' from current PO '%s' do not exist in HO PO '%s'."
                    ) % (
                                              ", ".join(extra_codes),
                                              self.name,
                                              self.invoice_number,
                                          ))
            if not order_id:
                self.ensure_one()
                partner_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                partner_domain = [('name', 'ilike', self.partner_id.name.strip())]
                encoded_domain = quote(str(partner_domain))
                partner_url = f"{partner_search}?domain={encoded_domain}&fields=['id','name']"
                partner_data = requests.get(partner_url, headers=headers_source).json()
                partner_id = partner_data.get("data", [])
                if not partner_id:
                    raise UserError(_("Partner '%s' not found in HO.") % self.partner_id.name)
                ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                picking_type_domain = [('name', '=', self.picking_type_id.name),
                                       ('company_id', '=', company_id[0]['id'])]
                picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
                picking_type = picking_type_data.get("data")
                unique_products = self.order_line.mapped('product_id')
                nhcl_ids = list(set(unique_products.mapped('nhcl_id')))

                product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"

                product_domain = [
                    ('nhcl_id', 'in', nhcl_ids)
                ]

                encoded_domain = quote(str(product_domain))

                product_search_url = (
                    f"{product_url}"
                    f"?domain={encoded_domain}"
                    f"&fields=['id','nhcl_id']"
                )

                product_response = requests.get(
                    product_search_url,
                    headers=headers_source
                ).json()

                ho_products = product_response.get("data", [])

                # ------------------------------------------------------------
                # Create mapping: nhcl_id -> product_id
                # ------------------------------------------------------------
                product_map = {
                    product['nhcl_id']: product['id']
                    for product in ho_products
                }

                # ------------------------------------------------------------
                # Prepare order lines
                # ------------------------------------------------------------
                order_lines = []

                for line in self.order_line:

                    ho_product_id = product_map.get(line.product_id.nhcl_id)

                    if not ho_product_id:
                        raise UserError(
                            _("Product '%s' not found in HO.")
                            % line.product_id.display_name
                        )

                    order_lines.append((0, 0, {
                        "name": line.name,
                        "product_id": ho_product_id,
                        "product_qty": line.product_qty,
                        "price_unit": line.price_unit,
                        "icode_barcode": line.icode_barcode,
                        "brand": line.brand,
                        "size": line.size,
                        "design": line.design,
                        "fit": line.fit,
                        "colour": line.color,
                        "product_excel": line.product_excel,
                        "standard_rate": line.standard_rate,
                        "mrp": line.mrp,
                        "rsp": line.rsp,
                        "item_vendor_id": line.item_vendor_id,
                        "hsn_sac_code": line.hsn_sac_code,
                        "des5": line.des5,
                        "des6": line.des6,
                        "mbq_plan": line.mbq_plan,
                    }))
                purchase_vals_data = {
                    'origin': self.name,
                    'partner_id': partner_id[0]['id'],
                    'nhcl_po_type': self.nhcl_po_type,
                    # 'picking_type_id': picking_type[0]['id'],
                    'date_order': self.date_order.strftime("%Y-%m-%d"),
                    'company_id': company_id[0]['id'],
                    'payment_term_id': self.payment_term_id.id,
                    'partner_ref': self.name,
                    'currency_id': self.currency_id.id,
                    'invoice_number':self.invoice_number,
                    'upload_type':self.upload_type,
                    'order_line': order_lines,
                }
                purchase_request_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/create"
                purchase_request_data = requests.post(purchase_request_search,
                                                      headers=headers_source, json=[purchase_vals_data])
                purchase_request_data.raise_for_status()
                # Access the JSON content from the response
                purchase_request = purchase_request_data.json()
                message = purchase_request.get("message", "No message provided")
                if purchase_request.get("success") == False:
                    _logger.info(
                        f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                    logging.error(
                        f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                    ho.create_cmr_transaction_server_replication_log('success', message)
                    ho.create_cmr_transaction_replication_log('Purchase Request',
                                                              self.id,self.name,
                                                              200,
                                                              'add', 'failure', message)
                else:
                    _logger.info(
                        f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    logging.info(
                        f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    ho.create_cmr_transaction_server_replication_log('success', message)
                    ho.create_cmr_transaction_replication_log('Purchase Request', self.id,self.name,
                                                              200,
                                                              'add', 'success',
                                                              f"Successfully created Purchase Order {self.name}")
                    self.nhcl_replication_status = True

    def update_purchase_request_to_ho(self):
        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        for ho in ho_id:
            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            api_key = ho.nhcl_api_key
            headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
            order_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
            company_domain = [('name', '=', self.company_id.name)]
            company_url = f"{company_search}?domain={company_domain}"
            company_data = requests.get(company_url, headers=headers_source).json()
            company_id = company_data.get("data")
            if not company_data.get('success'):
                ho_msg = company_data.get('message') or "HO API validation failed"
                raise ValidationError(f"HO Company: {ho_msg}")
            order_domain = [('origin', '=', self.name), ('company_id', '=', company_id[0]['id'])]
            order_url = f"{order_search}?domain={order_domain}"
            order_data = requests.get(order_url, headers=headers_source).json()
            order_id = order_data.get("data")
            print("order_id", order_id[0]['id'])
            order = order_id[0]['id']
            if order_id:
                self.ensure_one()
                partner_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                partner_domain = [('name', 'ilike', self.partner_id.name.strip())]
                encoded_domain = quote(str(partner_domain))
                partner_url = f"{partner_search}?domain={encoded_domain}"
                partner_data = requests.get(partner_url, headers=headers_source).json()
                partner_id = partner_data.get("data", [])
                if not partner_id:
                    raise UserError(_("Partner '%s' not found in HO.") % self.partner_id.name)
                ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                picking_type_domain = [('name', '=', self.picking_type_id.name),
                                       ('company_id', '=', company_id[0]['id'])]
                picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
                picking_type = picking_type_data.get("data")
                order_lines = []
                for line in self.order_line:
                    product_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                    product_domain = [('default_code', '=', line.product_id.default_code), ('nhcl_id', '=', line.product_id.nhcl_id)]
                    product_id_url = f"{product_url_data}?domain={product_domain}"
                    product_data = requests.get(product_id_url, headers=headers_source).json()
                    product_id = product_data.get("data")
                    if not product_id:
                        raise UserError(_('Product %s not found in HO') % line.product_id.display_name)
                    purchase_line_domain = [('product_id', '=', product_id[0]['id']),
                                            ('order_id', '=', order)]
                    po_line_url = f"http://{ho_ip}:{ho_port}/api/purchase.order.line/search"
                    purchase_order_line_url = f"{po_line_url}?domain={purchase_line_domain}"
                    purchase_order_line_data = requests.get(purchase_order_line_url, headers=headers_source).json()
                    purchase_order_line_id = purchase_order_line_data.get("data")
                    if purchase_order_line_id and line.name == purchase_order_line_id[0]['name']:
                        purchase_line_id = purchase_order_line_id[0]['id']
                        order_lines.append([1, purchase_line_id, {
                            "name": line.name,
                            "product_id": product_id[0]['id'],
                            "product_qty": line.product_qty,
                            "price_unit": line.price_unit,
                            "mbq_plan": line.mbq_plan,
                        }])
                    else:
                        order_lines.append((0, 0, {
                            "name": line.name,
                            "product_id": product_id[0]['id'],
                            "product_qty": line.product_qty,
                            "price_unit": line.price_unit,
                            "mbq_plan": line.mbq_plan,
                        }))
                purchase_vals_data = {
                    'id': order_id[0]['id'],
                    'order_line': order_lines
                }
                purchase_indent_domain = [('purchase_indent_id', '=', order_id[0]['id']), ]
                po_indent_url = f"http://{ho_ip}:{ho_port}/api/internal.purchase.indent.orderline/search"
                purchase_indent_line_url = f"{po_indent_url}?domain={purchase_indent_domain}"
                purchase_indent_line_data = requests.get(purchase_indent_line_url, headers=headers_source).json()
                purchase_indent_line_id = purchase_indent_line_data.get("data")
                if purchase_indent_line_id:
                    raise UserError(_('You are not allowed to update po data in HO, because PO added '
                                      'in Internal Purchase Indent in HO'))
                purchase_request_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/{order}"
                purchase_request_data = requests.put(purchase_request_search,
                                                     headers=headers_source, json=purchase_vals_data)
                purchase_request_data.raise_for_status()
                # Access the JSON content from the response
                purchase_request = purchase_request_data.json()
                message = purchase_request.get("message", "No message provided")
                if purchase_request.get("success") == False:
                    _logger.info(
                        f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                    logging.error(
                        f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                    ho.create_cmr_transaction_server_replication_log('success', message)
                    ho.create_cmr_transaction_replication_log('Purchase Request',
                                                             self.id,self.name,
                                                              200,
                                                              'add', 'failure', message)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'message': "Failed to Sync",
                            'type': 'danger',
                            'sticky': False
                        }
                    }
                else:
                    self.nhcl_update_status = True
                    _logger.info(
                        f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    logging.info(
                        f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    ho.create_cmr_transaction_server_replication_log('success', message)
                    ho.create_cmr_transaction_replication_log('Purchase Request', self.id,self.name,
                                                              200,
                                                              'add', 'success',
                                                              f"Successfully updated the Purchase Order {self.name}")
                    # return {
                    #     'type': 'ir.actions.client',
                    #     'tag': 'display_notification',
                    #     'params': {
                    #         'message': "Successfully Synced",
                    #         'type': 'success',
                    #         'sticky': False
                    #     }
                    # }

    # def button_cancel(self):
    #     res= super(PurchaseOrder, self).button_cancel()
    #     if self.state == 'cancel' and self.nhcl_replication_status == True:

    def cancel_purchase_request_to_ho(self):
        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        if self.state == 'cancel':
            for ho in ho_id:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
                order_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/search"
                company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                company_domain = [('name', '=', self.company_id.name)]
                company_url = f"{company_search}?domain={company_domain}"
                company_data = requests.get(company_url, headers=headers_source).json()
                company_id = company_data.get("data")
                if not company_data.get('success'):
                    ho_msg = company_data.get('message') or "HO API validation failed"
                    raise ValidationError(f"HO Company: {ho_msg}")
                order_domain = [('origin', '=', self.name), ('company_id', '=', company_id[0]['id'])]
                order_url = f"{order_search}?domain={order_domain}"
                order_data = requests.get(order_url, headers=headers_source).json()
                order_id = order_data.get("data")
                order = order_id[0]['id']
                if order_id:
                    self.ensure_one()
                    partner_search = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                    partner_domain = [('name', 'ilike', self.partner_id.name.strip())]
                    encoded_domain = quote(str(partner_domain))
                    partner_url = f"{partner_search}?domain={encoded_domain}"
                    partner_data = requests.get(partner_url, headers=headers_source).json()
                    partner_id = partner_data.get("data", [])
                    if not partner_id:
                        raise UserError(_("Partner '%s' not found in HO.") % self.partner_id.name)
                    purchase_vals_data = {
                        'id': order_id[0]['id'],
                        'state': self.state
                    }
                    purchase_indent_domain = [('purchase_indent_id', '=', order_id[0]['id']), ]
                    po_indent_url = f"http://{ho_ip}:{ho_port}/api/internal.purchase.indent.orderline/search"
                    purchase_indent_line_url = f"{po_indent_url}?domain={purchase_indent_domain}"
                    purchase_indent_line_data = requests.get(purchase_indent_line_url, headers=headers_source).json()
                    purchase_indent_line_id = purchase_indent_line_data.get("data")
                    if purchase_indent_line_id:
                        raise UserError(_('You are not allowed to Cancel po data in HO, because PO added '
                                          'in Internal Purchase Indent in HO'))
                    purchase_request_search = f"http://{ho_ip}:{ho_port}/api/purchase.order/{order}"
                    purchase_request_data = requests.put(purchase_request_search,
                                                         headers=headers_source, json=purchase_vals_data)
                    purchase_request_data.raise_for_status()
                    # Access the JSON content from the response
                    purchase_request = purchase_request_data.json()
                    message = purchase_request.get("message", "No message provided")
                    if purchase_request.get("success") == False:
                        _logger.info(
                            f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Purchase Request {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                        ho.create_cmr_transaction_server_replication_log('success', message)
                        ho.create_cmr_transaction_replication_log('Purchase Request',
                                                         self.id, self.name,
                                                                  200,
                                                                  'add', 'failure', message)
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'message': "Failed to Sync",
                                'type':'danger',
                                'sticky': False
                            }
                        }
                    else:
                        _logger.info(
                            f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f"Successfully created Purchase Request {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                        ho.create_cmr_transaction_server_replication_log('success', message)
                        ho.create_cmr_transaction_replication_log('Purchase Request', self.id,self.name,
                                                                  200,
                                                                  'add', 'success',
                                                                  f"Successfully cancel the Purchase Order {self.name}")
                        return {
                            'type' : 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'message': "Successfully Synced",
                                'type': 'success',
                                'sticky': False
                            }
                        }



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    icode_barcode = fields.Char("Barcode")
    # article_name = fields.Char("Article Name")
    brand = fields.Char("Brand")
    size = fields.Char("Size")
    design = fields.Char("Design")
    fit = fields.Char("Fit")
    color = fields.Char("Colour")
    product_excel = fields.Char("Product (Excel)")
    standard_rate = fields.Float("Standard Rate")
    mrp = fields.Float("MRP")
    rsp = fields.Float("RSP")
    item_vendor_id = fields.Char("Item Vendor ID")
    hsn_sac_code = fields.Char("HSN/SAC Code")
    des5 = fields.Char("Aging")
    des6 = fields.Char("DES6")
    divison = fields.Many2one('product.category', string="Divison", compute="_compute_categories", store=True)
    section = fields.Many2one('product.category', string="Section", compute="_compute_categories", store=True)
    department = fields.Many2one('product.category', string="Department", compute="_compute_categories", store=True)
    brick = fields.Many2one('product.category', string="Brick", compute="_compute_categories", store=True)
    issued_qty = fields.Float(string="Received Qty", compute='_compute_issued_qty')
    diff_qty = fields.Float(string="Balance Qty", compute='_compute_balance_status')
    status = fields.Selection([('pending', 'Pending'), ('partial', 'Partial'), ('done', 'Done')],
                              string="Status", compute='_compute_balance_status')
    nhcl_onhand_qty = fields.Float(string="Onhand Qty", related="product_id.qty_available")
    mbq_plan = fields.Char(string="MBQ Plan")
    mbq_max_qty = fields.Float(string="MBQ Max Qty")
    offer_id = fields.Many2one('offer.master', string="Offer")

    def action_open_replenishment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Replenishment Details',
            'res_model': 'replenishment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
                'default_purchase_line_id': self.id,
            }
        }

    @api.depends('product_id', 'order_id.name')
    def _compute_issued_qty(self):
        Lot = self.env['stock.lot']
        data = {}
        products = self.mapped('product_id').ids
        refs = self.mapped('order_id.name')

        domain = [
            ('product_id', 'in', products),
            ('nhcl_purchase_indent_reference', 'in', refs)
        ]
        lots = Lot.search(domain)
        # aggregate manually
        for lot in lots:
            key = (lot.product_id.id, lot.nhcl_purchase_indent_reference)
            data[key] = data.get(key, 0.0) + lot.product_qty
        # assign to lines
        for line in self:
            line.issued_qty = data.get(
                (line.product_id.id, line.order_id.name),
                0.0
            )

    @api.depends('product_qty', 'issued_qty')
    def _compute_balance_status(self):
        for line in self:
            issued = line.issued_qty or 0.0
            qty = line.product_qty or 0.0
            diff = qty - issued
            line.diff_qty = diff
            if float_compare(issued, 0.0, precision_rounding=2) == 0:
                line.status = 'pending'
            elif float_compare(issued, qty, precision_rounding=2) < 0:
                line.status = 'partial'
            else:
                line.status = 'done'

    @api.depends('product_id')
    def _compute_categories(self):
        for rec in self:
            categ = rec.product_id.categ_id

            if not categ:
                continue

            if not rec.brick:
                rec.brick = categ.id

            parent = categ.parent_id
            if parent and not rec.department:
                rec.department = parent.id

            parent2 = parent.parent_id if parent else False
            if parent2 and not rec.section:
                rec.section = parent2.id

            parent3 = parent2.parent_id if parent2 else False
            if parent3 and not rec.divison:
                rec.divison = parent3.id





