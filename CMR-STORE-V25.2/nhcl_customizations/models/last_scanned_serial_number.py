from odoo import models,fields,api
import requests
import logging

_logger = logging.getLogger(__name__)

class LastScannedSerialNumber(models.Model):
    _name = "last.scanned.serial.number"
    _description = "last scanned serial number"

    receipt_number = fields.Char(string="Receipt Number")
    document_number = fields.Char(string="HO Delivery Doc")
    stock_serial = fields.Char(string="Serial's", copy=False)
    stock_product_barcode = fields.Char(string="Barcode", copy=False)
    stock_qty = fields.Float(string='Qty', copy=False)
    store_name = fields.Char(string="Store Name")
    # date = fields.Date(string="Date")
    state = fields.Boolean(string="Verification Done")
    sent_done = fields.Boolean(string="Sent Done")
    store_id = fields.Many2one('res.company', string='Store', default=lambda self: self.env.company.id)
    type_product = fields.Selection([('brand', 'Brand'), ('un_brand', 'Un Brand'),
                                     ('others', 'Others')], string='Type Product')

    def get_missing_serial_numbers(self):
        ho_id = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True),
        ], limit=1)
        if not ho_id:
            return

        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            headers_source = {
                'api-key': f"{ho_api_key}",
                'Content-Type': 'application/json'
            }

            # Collect missing serial numbers
            missing_serial_number_lines = self.env['last.scanned.serial.number'].sudo().search([
                ('state', '=', False),('sent_done', '=', False)
            ])
            if not missing_serial_number_lines:
                _logger.info("No missing serial numbers found.")
                return
            ho_store_pos_url_data = f"http://{ho_ip}:{ho_port}/api/stock.verification.unmatched/create"
            serial_number_data_list = []
            for line in missing_serial_number_lines:
                if not line.stock_serial and not line.stock_product_barcode:
                    continue
                # company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                # company_domain = [('name', '=', line.store_id.name)]
                # company_url = f"{company_search}?domain={company_domain}"
                # company_data = requests.get(company_url, headers=headers_source).json()
                # company_id = company_data.get("data")
                # --- Step 3: Build payload with company_id ---
                serial_number_data_list = {
                    'store_name': line.store_name,
                    'serial_number': line.stock_serial if line.stock_serial else False,
                    'barcode': line.stock_product_barcode if line.stock_product_barcode else False,
                    'store_receipt_number': line.receipt_number,
                    'ho_delivery_number': line.document_number,
                    'store_date':line.create_date.strftime('%Y-%m-%d %H:%M:%S') if line.create_date else False

                }
                print("serial data",serial_number_data_list)
                # API endpoint to create stock.verification in HO


                try:
                    move_data = requests.post(
                        ho_store_pos_url_data,
                        headers=headers_source,
                        json=serial_number_data_list
                    )
                    response_json = move_data.json()
                    print(response_json)
                    message = response_json.get("message", "No message provided")

                    if response_json.get('success'):
                        _logger.info(f"Successfully created Records {message}")
                        print("success")
                        self.sent_done = True
                        # ho_id.create_cmr_transaction_server_replication_log('success', 'Server Connected Successfully')
                        # for line in missing_serial_number_lines:
                        #     ho_id.create_cmr_transaction_replication_log(
                        #         response_json.get('object_name'),
                        #         line.id,
                        #         200,
                        #         'add',
                        #         'success',
                        #         "Successfully created in bulk."
                        #     )
                    else:
                        _logger.error(f"Failed to create Records: {message}")
                        # ho_id.create_cmr_transaction_server_replication_log('success', message)
                        # for line in missing_serial_number_lines:
                        #     ho_id.create_cmr_transaction_replication_log(
                        #         response_json.get('object_name'),
                        #         line.id,
                        #         200,
                        #         'add',
                        #         'failure',
                        #         message
                        #     )
                except Exception as e:
                    ho_id.create_cmr_transaction_server_replication_log("failure", str(e))
                    # for line in missing_serial_number_lines:
                    #     ho_id.create_cmr_transaction_replication_log(
                    #         'stock.verification',
                    #         line.id,
                    #         500,
                    #         'add',
                    #         'failure',
                    #         str(e)
                    #     )

        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))