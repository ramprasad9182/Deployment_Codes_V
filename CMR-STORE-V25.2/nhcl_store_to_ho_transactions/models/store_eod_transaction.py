from odoo import models
import requests
import logging

_logger = logging.getLogger(__name__)
from datetime import datetime
from odoo.exceptions import ValidationError, UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def get_pos_journal_entry(self):
        ho_ids = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_ids:
            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            ho_api_key = ho.nhcl_api_key
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            store_journal_entries = self.env['account.move'].search([
                ('nhcl_replication_status', '=', False)
            ])

            if not store_journal_entries:
                continue

            for entry in store_journal_entries:
                if entry.journal_id.name != "Credit Note Issue":
                    try:
                        # -------------------- Company --------------------
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', entry.company_id.name)]
                        company_url = f"{company_search}?domain={company_domain}"
                        company_data = requests.get(company_url, headers=headers_source).json()
                        company_id = company_data.get("data")

                        if not company_id:
                            msg = f"Company not found for Journal Entry {entry.name}"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                        # -------------------- Journal --------------------
                        journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        journal_domain = [('name', '=', entry.journal_id.name), ('company_id', '=', company_id[0]['id'])]
                        journal_url = f"{journal_search}?domain={journal_domain}"
                        journal_data = requests.get(journal_url, headers=headers_source).json()
                        account_journal = journal_data.get("data")

                        # Fallback: try parent company
                        if not account_journal and company_id and company_id[0].get('parent_id'):
                            parent_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                            parent_journal_domain = [
                                ('name', '=', entry.journal_id.name),
                                ('company_id.name', '=', company_id[0]['parent_id'][0]['name'])
                            ]
                            parent_journal_url = f"{parent_journal_search}?domain={parent_journal_domain}"
                            parent_journal_data = requests.get(parent_journal_url, headers=headers_source).json()
                            account_journal = parent_journal_data.get("data")

                        if not account_journal:
                            msg = f"Journal not found for entry {entry.name}"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                        # -------------------- Prepare Move Lines --------------------
                        invoice_lines = []
                        for line in entry.line_ids:
                            try:
                                account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                account_domain = [
                                    ('name', '=', line.account_id.name),
                                    ('company_id', '=', company_id[0]['id'])
                                ]
                                account_url = f"{account_search}?domain={account_domain}"
                                account_data = requests.get(account_url, headers=headers_source).json()
                                account_id = account_data.get("data")

                                # Fallback: try parent company
                                if not account_id and company_id and company_id[0].get('parent_id'):
                                    parent_account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                    parent_account_domain = [
                                        ('name', '=', line.account_id.name),
                                        ('company_id', '=', company_id[0]['parent_id'][0]['id'])
                                    ]
                                    parent_account_url = f"{parent_account_search}?domain={parent_account_domain}"
                                    parent_account_data = requests.get(parent_account_url, headers=headers_source).json()
                                    account_id = parent_account_data.get("data")

                                if not account_id:
                                    msg = f"Account not found for line '{line.name}' in entry {entry.name}"
                                    ho.create_cmr_transaction_server_replication_log("failure", msg)
                                    continue

                                invoice_lines.append((0, 0, {
                                    "name": line.name or '',
                                    "account_id": account_id[0]['id'],
                                    "debit": line.debit,
                                    "credit": line.credit,
                                }))
                            except Exception as line_err:
                                msg = f"Error processing line in entry {entry.name}: {line_err}"
                                ho.create_cmr_transaction_server_replication_log("failure", msg)
                                continue

                        if not invoice_lines:
                            msg = f"No valid account lines found for entry {entry.name}"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                        # -------------------- Check if already exists --------------------
                        if entry.journal_id.name == "Cash":
                            move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                            move_domain = [('name', '=', entry.name), ('company_id', '=', company_id[0]['id'])]
                            move_url = f"{move_search}?domain={move_domain}"
                            move_data = requests.get(move_url, headers=headers_source).json()
                            existing_move = move_data.get("data")
                        else:
                            move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                            move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                            move_url = f"{move_search}?domain={move_domain}"
                            move_data = requests.get(move_url, headers=headers_source).json()
                            existing_move = move_data.get("data")
                        if existing_move:
                            msg = f"Journal Entry {entry.name} already exists in HO"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                        # -------------------- Create Journal Entry --------------------
                        move_vals = {
                            "name": entry.name,
                            "ref": entry.ref,
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "move_type": entry.move_type,
                            "journal_id": account_journal[0]['id'],
                            "amount_total": entry.amount_total,
                            "company_id": company_id[0]['id'],
                            'nhcl_store_je': True,
                            'line_ids': invoice_lines
                        }

                        try:
                            ho_move_url = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            move_response = requests.post(ho_move_url, headers=headers_source, json=[move_vals])
                            move_response.raise_for_status()
                            response_json = move_response.json()

                            if response_json.get("success"):
                                entry.nhcl_replication_status = True
                                msg = f"Successfully created Journal Entry {entry.name}"
                                ho.create_cmr_transaction_server_replication_log("success", msg)
                                ho.create_cmr_transaction_replication_log(
                                    'POS Journal Entry', entry.id,entry.name, 200, 'add', 'success', msg
                                )
                            else:
                                msg = f"Failed to create Journal Entry {entry.name}: {response_json.get('message', '')}"
                                ho.create_cmr_transaction_server_replication_log("failure", msg)
                                ho.create_cmr_transaction_replication_log(
                                    'POS Journal Entry', entry.id, entry.name, 200, 'add', 'failure', msg
                                )

                        except Exception as api_err:
                            msg = f"API Error creating entry {entry.name}: {api_err}"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                    except Exception as entry_err:
                        msg = f"Unexpected error while processing {entry.name}: {entry_err}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue


    def get_pos_delivery_orders(self):
        ho_ids = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_ids:
            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            store_api_key = ho.nhcl_api_key
            headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

            picking_type_id = self.env['stock.picking.type'].search([('name', '=', "PoS Orders")])
            store_pos_delivery_orders = self.env['stock.picking'].search([
                ('picking_type_id', '=', picking_type_id.id),
                ('nhcl_replication_status', '=', False),
                ('state', '=', 'done')
            ])
            # store_pos_delivery_orders = self.env['stock.picking'].search([
            #     ('name', '=', 'CMR-H/POS/00567'),
            #     ('nhcl_replication_status', '=', False),
            #     ('state', '=', 'done')
            # ])

            if not store_pos_delivery_orders:
                continue

            for order in store_pos_delivery_orders:
                try:
                    if order.location_dest_id.name != "Customers":
                        continue

                    # -------------------- Company --------------------
                    company_url = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', order.company_id.name)]
                    company_data = requests.get(
                        f"{company_url}?domain={company_domain}", headers=headers_source
                    ).json()
                    company_id = company_data.get("data")
                    if not company_id:
                        msg = f"Company not found for order: {order.name}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    # -------------------- Picking Type --------------------
                    picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                    picking_type_domain = [('name', '=', "PoS Orders"), ('company_id', '=', company_id[0]['id'])]
                    picking_type_data = requests.get(
                        f"{picking_type_url}?domain={picking_type_domain}", headers=headers_source
                    ).json()
                    picking_type = picking_type_data.get("data")
                    if not picking_type:
                        msg = f"Picking Type not found for company {order.company_id.name}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    # -------------------- Source Location --------------------
                    location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                    location_domain = [
                        ('name', '=', order.location_id.name),
                        ('active', '!=', False),
                        ('usage', '=', 'internal'),
                        ('company_id', '=', company_id[0]['id'])
                    ]
                    location_data = requests.get(
                        f"{location_url}?domain={location_domain}", headers=headers_source
                    ).json()
                    location_id = location_data.get("data")
                    if not location_id:
                        msg = f"Source Location not found for order: {order.name}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    # -------------------- Destination Location --------------------
                    dest_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                    dest_domain = [
                        ('complete_name', '=', order.location_dest_id.complete_name),
                        ('active', '!=', False),
                        ('usage', '=', 'customer')
                    ]
                    dest_data = requests.get(
                        f"{dest_location_url}?domain={dest_domain}", headers=headers_source
                    ).json()
                    dest_location = dest_data.get("data")
                    if not dest_location:
                        msg = f"Destination Location not found for order: {order.name}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    # -------------------- Create Picking --------------------
                    stock_picking_vals = {
                        'picking_type_id': picking_type[0]['id'],
                        'origin': order.name,
                        'location_id': location_id[0]['id'],
                        'location_dest_id': dest_location[0]['id'],
                        'company_id': company_id[0]['id'],
                        'move_type': 'direct',
                        'state': 'done',
                        'nhcl_store_delivery': True
                    }

                    try:
                        picking_response = requests.post(
                            f"http://{ho_ip}:{ho_port}/api/stock.picking/create",
                            headers=headers_source, json=[stock_picking_vals]
                        )
                        picking_response.raise_for_status()
                        stock_picking = picking_response.json()
                    except Exception as req_err:
                        msg = f"Error creating picking for {order.name}: {req_err}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    if not stock_picking.get("success"):
                        msg = f"Picking creation failed for order {order.name}: {stock_picking.get('message')}"
                        ho.create_cmr_transaction_server_replication_log("failure", msg)
                        continue

                    picking_id = stock_picking.get("create_id")

                    # -------------------- Create Move Lines --------------------
                    for line in order.move_line_ids_without_package:
                        try:
                            product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                            product_data = requests.get(
                                f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}",
                                headers=headers_source
                            ).json()
                            product_id = product_data.get("data")
                            if not product_id:
                                msg = f"Product not found for {line.product_id.display_name} in order {order.name}"
                                ho.create_cmr_transaction_server_replication_log("failure", msg)
                                continue

                            lot_name = line.lot_id.name if line.lot_id else None
                            move_line_vals = {
                                "picking_id": picking_id,
                                "product_id": product_id[0]['id'],
                                "quantity": line.quantity,
                                "location_id": location_id[0]['id'],
                                "location_dest_id": dest_location[0]["id"],
                                "lot_name": lot_name,
                            }

                            move_resp = requests.post(
                                f"http://{ho_ip}:{ho_port}/api/stock.move.line/create",
                                headers=headers_source, json=[move_line_vals]
                            )
                            move_resp.raise_for_status()

                        except Exception as line_err:
                            msg = f"Move line creation failed for {order.name}: {line_err}"
                            ho.create_cmr_transaction_server_replication_log("failure", msg)
                            continue

                    # -------------------- Success Marking --------------------
                    order.nhcl_replication_status = True
                    order.validate_orders(deliver_order='pos_order')
                    msg = f"Delivery Order successfully created for {order.name}"
                    ho.create_cmr_transaction_server_replication_log("success", msg)

                except Exception as order_err:
                    # Any unexpected error per order
                    ho.create_cmr_transaction_server_replication_log("failure", str(order_err))
                    continue


    def get_pos_bank_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Bank")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Bank'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Bank'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS Bank Journal Entry', entry.id, entry.name, 200, 'add',
                                                                                      'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS Bank Journal Entry', entry.id, entry.name, 200, 'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)

                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_cash_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Cash")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Cash'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Cash'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id'] :
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('name', '=', entry.name), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS Cash Journal Entry', entry.id, entry.name, 200, 'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS Cash Journal Entry', entry.id, entry.name, 200, 'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_hdfc_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "HDFC")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'HDFC'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'HDFC'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS HDFC Journal Entry', entry.id, entry.name, 200, 'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS HDFC Journal Entry', entry.id, entry.name, 200, 'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_bajaj_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "BAJAJ")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'BAJAJ'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'BAJAJ'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS Bajaj Journal Entry',
                                                                                     entry.id,entry.name,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS Bajaj Journal Entry',
                                                                                     entry.id,entry.name,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_mobikwik_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Mobikwik")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Mobikwik'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Mobikwik'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS Mobikwik Journal Entry',
                                                                                     entry.id,entry.name,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS Mobikwik Journal Entry',
                                                                                     entry.id,entry.name,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_sbi_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "SBI")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'SBI'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'SBI'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_paytm_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Paytm")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Paytm'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Paytm'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_axis_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Axis")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Axis'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Axis'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_cheque_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Cheque")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Cheque'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Cheque'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_credit_note_settlement_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Credit Note Settlement")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Credit Note Settlement'),
                                              ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Credit Note Settlement'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_gift_voucher_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Gift Voucher")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            if store_journal_entry:
                for entry in store_journal_entry:
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Gift Voucher'), ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")
                    if not account_journal and company_id and company_id[0]['parent_id']:
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Gift Voucher'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")
                    tax_id_var = False
                    invoice_lines = []
                    for line in entry.line_ids:
                        # if line.tax_line_id and tax_id_var == False:
                        #     tax_id_var = True
                        # if tax_id_var == True:

                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url,
                                                    headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id and company_id and company_id[0]['parent_id']:
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url,
                                                               headers=headers_source).json()
                            account_id = parent_account_data.get("data")
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "account_id": account_id[0]['id'],
                            "debit": line.debit,
                            "credit": line.credit,
                        }))
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url,
                                                     headers=headers_source).json()
                    move_id = account_move_data.get("data")
                    try:
                        if not move_id:
                            move_vals = {
                                "name": entry.name,
                                "ref": entry.ref,
                                "date": entry.date.strftime("%Y-%m-%d"),
                                "move_type": entry.move_type,
                                "journal_id": account_journal[0]['id'],
                                "amount_total": entry.amount_total,
                                "company_id": company_id[0]['id'],
                                'nhcl_store_je': True,
                                'line_ids': invoice_lines
                            }
                            ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                            try:
                                move_data = requests.post(ho_move_url_data, headers=headers_source,
                                                          json=[move_vals])
                                move_data.raise_for_status()
                                print(move_data)
                                # Access the JSON content from the response
                                response_json = move_data.json()
                                print('response_json', response_json)
                                if response_json:
                                    message = response_json.get("message", "No message provided")
                                    if response_json['success'] == True:
                                        entry.nhcl_replication_status = True
                                        _logger.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {entry.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {entry.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                     entry.id,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            except Exception as e:
                                ho_id.create_cmr_transaction_server_replication_log("failure", e)
                        # if move_id.line_ids:
                        #     move_id.action_post()
                    except:
                        _logger.info(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to create Journal Entry'{ho_ip}' with partner '{ho_port}'. Error:")
        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_exchange_recipts_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetch the correct picking type for "Product Exchange - POS"
                picking_type_id = self.env['stock.picking.type'].search([('name', '=', "Product Exchange - POS")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
                     ('state', '=', 'done')])

                if store_pos_delivery_orders:
                    try:
                        for order in store_pos_delivery_orders:
                            if order.location_id.name == "Customers":
                                # Fetch the company from HO
                                company_url = f"http://{ho_ip}:{ho_port}/api/res.company/search?domain=[('name','=', '{order.company_id.name}')]"
                                company_data = requests.get(company_url, headers=headers_source).json()
                                company_id = company_data.get("data", [])

                                if not company_id:
                                    logging.warning(
                                        f"Company {order.company_id.name} not found in HO. Skipping order {order.name}.")
                                    continue  # Skip this order and move to the next one

                                company_id = company_id[0]['id']
                                print("company_idjjhjj",company_id)
                                # Fetch the location from HO
                                location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('complete_name','=', '{order.location_id.complete_name}'),('active','!=',False)]"
                                location_data = requests.get(location_url, headers=headers_source).json()
                                location_id = location_data.get("data", [])

                                if not location_id:
                                    logging.warning(
                                        f"Location {order.location_id.name} not found in HO. Skipping order {order.name}.")
                                    continue  # Skip this order and move to the next one

                                location_id = location_id[0]['id']

                                # Fetch the destination location from HO
                                dest_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('complete_name','=', '{order.location_dest_id.complete_name}'),('active','!=',False)]"
                                dest_location_data = requests.get(dest_location_url, headers=headers_source).json()
                                dest_location_id = dest_location_data.get("data", [])

                                if not dest_location_id:
                                    logging.warning(
                                        f"Destination Location {order.location_dest_id.complete_name} not found in HO. Skipping order {order.name}.")
                                    continue  # Skip this order and move to the next one

                                dest_location_id = dest_location_id[0]['id']

                                # Fetch or create the partner in HO
                                partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{order.partner_id.name}'),('phone','=', '{order.partner_id.phone}'),('company_id','=', {company_id})]"
                                partner_data = requests.get(partner_url, headers=headers_source).json()
                                partner = partner_data.get("data", [])

                                if not partner:
                                    line_partner_category_data = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
                                    line_partner_category_data_domain = [('name', '=', 'Customer')]
                                    line_partner_category_data_url = f"{line_partner_category_data}?domain={line_partner_category_data_domain}"
                                    pos_partner_category = requests.get(line_partner_category_data_url, headers=headers_source).json()
                                    pos_partner_category_id = None
                                    if pos_partner_category and pos_partner_category.get("data"):
                                        pos_partner_category_id = pos_partner_category.get("data")[0]['id']
                                    partner_data = {
                                        'name': order.partner_id.name,
                                        'phone': order.partner_id.phone,
                                        'company_id': company_id,
                                        'group_contact': pos_partner_category_id
                                    }
                                    partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                                    partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                            json=[partner_data])
                                    partner_create_response.raise_for_status()
                                    partner = partner_create_response.json().get("create_id")

                                partner_id = partner[0]['id'] if partner else partner

                                # Fetch or create the Picking Type ID in HO
                                picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search?domain=[('name','=', '{order.picking_type_id.name}'),('company_id','=', {company_id})]"
                                picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
                                picking_type = picking_type_data.get("data", [])
                                # Determine the stock picking data based on 'same store' or 'other store'
                                if order.company_type == 'same':
                                    stock_picking_data = {
                                        'partner_id': partner_id,
                                        'picking_type_id': picking_type[0]["id"],
                                        'origin': order.name,
                                        'location_id': location_id,
                                        'location_dest_id': dest_location_id,
                                        'company_id': company_id,
                                        'stock_type': 'pos_exchange',
                                        'company_type': order.company_type,
                                        'nhcl_store_delivery': True
                                    }
                                    print("stock_picking_data",stock_picking_data)
                                else:  # For "other store"
                                    # other_store_url = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search?domain=[('nhcl_store_name','=', '{order.store_name}')]"
                                    # other_store_data = requests.get(other_store_url, headers=headers_source).json()
                                    # other_store_id = other_store_data.get("data", [])
                                    #
                                    # if not other_store_id:
                                    #     logging.warning(
                                    #         f"Other store {order.store_name.name} not found in HO. Skipping order {order.name}.")
                                    #     continue  # Skip this order and move to the next one
                                    #
                                    # other_store_id = other_store_id[0]["id"]

                                    stock_picking_data = {
                                        'partner_id': partner_id,
                                        'picking_type_id': picking_type[0]["id"],
                                        'origin': order.name,
                                        'location_id': location_id,
                                        'location_dest_id': dest_location_id,
                                        'company_id': company_id,
                                        'store_name': 2,
                                        'stock_type': 'pos_exchange',
                                        'company_type': order.company_type,
                                        'store_pos_order': order.store_pos_order,
                                        'nhcl_store_delivery': True
                                    }

                                # Create stock picking in HO
                                stock_picking_create_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/create"
                                stock_picking_create_response = requests.post(stock_picking_create_url,
                                                                              headers=headers_source,
                                                                              json=[stock_picking_data])
                                stock_picking_create_response.raise_for_status()

                                stock_picking = stock_picking_create_response.json()
                                stock_picking_id = stock_picking.get("create_id")
                                if not stock_picking_id:
                                    logging.warning(f"Failed to create stock picking for order {order.name}. Skipping.")
                                    continue  # Skip this order and move to the next one

                                # Create stock move lines
                                for line in order.move_line_ids_without_package:
                                    product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                                    product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"
                                    product_data = requests.get(product_url, headers=headers_source).json()
                                    product_id = product_data.get("data", [])

                                    if not product_id:
                                        logging.warning(
                                            f"Product {line.product_id.name} not found in HO. Skipping move line for order {order.name}.")
                                        continue  # Skip this move line and move to the next

                                    product_id = product_id[0]['id']
                                    cost_price = line.cost_price
                                    print("cost_price",cost_price)
                                    move_line_vals = {
                                        "picking_id": stock_picking_id,
                                        "product_id": product_id,
                                        "cost_price": cost_price,
                                        # "mr_price": line.mr_price,
                                        # "rs_price": line.rs_price,
                                        # "internal_ref_lot": line.internal_ref_lot,
                                        # "type_product": line.type_product,
                                        "quantity": line.quantity,
                                        "location_id": location_id,
                                        "location_dest_id": dest_location_id,
                                        "lot_name": line.lot_id.name if line.lot_id else None
                                    }
                                    print("move_line_vals",move_line_vals)

                                    stock_move_line_url = f"http://{ho_ip}:{ho_port}/api/stock.move.line/create"
                                    stock_move_line_response = requests.post(stock_move_line_url, headers=headers_source,
                                                                             json=[move_line_vals])
                                    stock_move_line_response.raise_for_status()
                                    response_json = stock_move_line_response.json()
                                    if response_json:
                                        message = response_json.get("message", "No message provided")
                                        if response_json['success'] == True:
                                            order.nhcl_replication_status = True
                                            _logger.info(
                                                f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                            logging.info(
                                                f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                            ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                                'Server Connected Successfully')
                                            ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                         order.id,
                                                                                         200,
                                                                                         'add', 'success',
                                                                                         f"Successfully created Journal Entry {order.name}")

                                        else:
                                            _logger.info(
                                                f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                            logging.error(
                                                f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                            ho_id.create_cmr_transaction_server_replication_log('success', message)
                                            ho_id.create_cmr_transaction_replication_log(response_json['object_name'],
                                                                                         order.id,
                                                                                         200,
                                                                                         'add', 'failure', message)

                            else:
                                logging.warning(f"Skipping order {order.name}, location not 'Customers'.")
                    except Exception as e:
                        logging.error(f"Error while processing order {order.name}: {e}")
                        ho.create_cmr_transaction_server_replication_log("failure", str(e))
                        ho.create_cmr_transaction_replication_log('error', order.id, 500, 'add', 'failure', str(e))

            except Exception as e:
                logging.error(f"Error while processing order {order.name}: {e}")
                ho.create_cmr_transaction_server_replication_log("failure", str(e))
                ho.create_cmr_transaction_replication_log('error', order.id, 500, 'add', 'failure', str(e))

    def get_pos_crediet_note_issue_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Credit Note Issue")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])

            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            if store_journal_entry:
                for entry in store_journal_entry:
                    print("Processing entry:", entry)

                    # Fetch company details
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    print('entry',entry.name)
                    # Fetch the corresponding journal entry
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Credit Note Issue'),
                                              ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")

                    if not account_journal and company_id and company_id[0]['parent_id']:
                        # Fetch parent journal entry if not found
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Credit Note Issue'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")

                    # Fetch or create the partner in HO
                    partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{entry.partner_id.name}'),('phone','=', '{entry.partner_id.phone}')]"
                    partner_data = requests.get(partner_url, headers=headers_source).json()
                    partner = partner_data.get("data", [])
                    new_partner = False
                    if not partner:
                        partner_data = {
                            'name': entry.partner_id.name,
                            'phone': entry.partner_id.phone,
                            # 'company_id': company_id
                        }
                        partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                        partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                json=[partner_data])
                        partner_create_response.raise_for_status()
                        new_partner = partner_create_response.json().get("create_id")

                    partner_id = partner[0]['id'] if partner else new_partner

                    # Prepare invoice lines
                    invoice_lines = []
                    service = entry.invoice_line_ids.filtered_domain(
                        [('product_id.detailed_type', '=', 'service')])

                    for line in entry.invoice_line_ids:
                        if service:
                            product_domain = [('name', '=', line.product_id.name)]
                        else:
                            product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                        product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"
                        product_data = requests.get(product_url, headers=headers_source).json()
                        product_id = product_data.get("data", [])

                        if not product_id:
                            logging.warning(
                                f"Product {line.product_id.name} not found in HO. Skipping move line for order {entry.name}.")
                            continue

                        product_id = product_id[0]['id']
                        tax_ids = False
                        if not service:
                            # Handle tax IDs
                            tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                            tax_domain = [('name', '=', f"{line.tax_ids.name}-CREDIT"), ('company_id', '=', company_id[0]['id']), ('nhcl_creadit_note_tax','=',True)]
                            tax_id_url = f"{tax_url_data}?domain={tax_domain}"
                            account_data = requests.get(tax_id_url, headers=headers_source).json()
                            tax_id = account_data.get("data")
                            if not tax_id and company_id:
                                # Fetch parent account if not found
                                parent_tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                parent_tax_domain = [('name', '=', f"{line.tax_ids.name}-CREDIT"),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id']), ('nhcl_creadit_note_tax','=',True)]
                                parent_tax_id_url = f"{parent_tax_url_data}?domain={parent_tax_domain}"
                                parent_tax_data = requests.get(parent_tax_id_url, headers=headers_source).json()
                                tax_id = parent_tax_data.get("data")
                            tax_ids = [(6, 0, [tax['id'] for tax in tax_id])] if tax_id else []

                        # Handle account ID
                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url, headers=headers_source).json()
                        account_id = account_data.get("data")

                        if not account_id and company_id:
                            # Fetch parent account if not found
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url, headers=headers_source).json()
                            account_id = parent_account_data.get("data")

                        # Add invoice line to the list
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "product_id": product_id,
                            "account_id": account_id[0]['id'],
                            "tax_ids": tax_ids if tax_ids else False,
                            "price_unit": line.price_unit,
                            "quantity": line.quantity,
                            # "price_subtotal": line.price_subtotal,
                        }))

                    # Search for existing move
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('name', '=', entry.name), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url, headers=headers_source).json()
                    move_id = account_move_data.get("data")

                    if not move_id:
                        # If no move found, create a new one
                        move_vals = {
                            "partner_id": partner_id,
                            "name": entry.name,
                            "ref": entry.name,
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "move_type": entry.move_type,
                            "journal_id": account_journal[0]['id'],
                            "amount_total": entry.amount_total,
                            "company_id": company_id[0]['id'],
                            'nhcl_store_je': True,
                            'invoice_line_ids': invoice_lines
                        }
                        print("Sending journal entry data:", move_vals)
                        ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                        try:
                            move_data = requests.post(ho_move_url_data, headers=headers_source, json=[move_vals])
                            move_data.raise_for_status()

                            response_json = move_data.json()
                            print('Journal entry creation response:', response_json)

                            if response_json and response_json['success']:
                                entry.nhcl_replication_status = True

                            else:
                                logging.error(f"Failed to create Journal Entry {entry.name}. Response: {response_json}")

                        except requests.exceptions.RequestException as e:
                            logging.error(f"Error while creating journal entry for {entry.name}: {str(e)}")
                            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

            else:
                logging.info("No journal entries found for replication.")

        except Exception as e:
            logging.error(f"General error during journal entry processing: {str(e)}")
            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

    def get_pos_cash_discount_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key
            account_journal_id = self.env['account.journal'].search([('name', '=', "Cash Discount")], limit=1)
            store_journal_entry = self.env['account.move'].search(
                [('journal_id', '=', account_journal_id.id), ('nhcl_replication_status', '=', False)])

            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            if store_journal_entry:
                for entry in store_journal_entry:
                    print("Processing entry:", entry)

                    # Fetch company details
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    print('entry',entry.name)
                    # Fetch the corresponding journal entry
                    account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    account_journal_domain = [('name', '=', 'Cash Discount'),
                                              ('company_id', '=', company_id[0]['id'])]
                    account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"
                    account_journal_data = requests.get(account_journal_url, headers=headers_source).json()
                    account_journal = account_journal_data.get("data")

                    if not account_journal and company_id and company_id[0]['parent_id']:
                        # Fetch parent journal entry if not found
                        parent_account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_account_journal_domain = [('name', '=', 'Cash Discount'),
                                                         ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                        parent_account_journal_url = f"{parent_account_journal_search}?domain={parent_account_journal_domain}"
                        parent_account_journal_data = requests.get(parent_account_journal_url,
                                                                   headers=headers_source).json()
                        account_journal = parent_account_journal_data.get("data")

                    # Fetch or create the partner in HO
                    partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{entry.partner_id.name}'),('phone','=', '{entry.partner_id.phone}')]"
                    partner_data = requests.get(partner_url, headers=headers_source).json()
                    partner = partner_data.get("data", [])
                    new_partner = False
                    if not partner:
                        partner_data = {
                            'name': entry.partner_id.name,
                            'phone': entry.partner_id.phone,
                            # 'company_id': company_id
                        }
                        partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                        partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                json=[partner_data])
                        partner_create_response.raise_for_status()
                        new_partner = partner_create_response.json().get("create_id")

                    partner_id = partner[0]['id'] if partner else new_partner

                    # Prepare invoice lines
                    invoice_lines = []
                    service = entry.invoice_line_ids.filtered_domain(
                        [('product_id.detailed_type', '=', 'service')])

                    for line in entry.invoice_line_ids:
                        if service:
                            product_domain = [('name', '=', line.product_id.name)]
                        else:
                            product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                        product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"
                        product_data = requests.get(product_url, headers=headers_source).json()
                        product_id = product_data.get("data", [])

                        if not product_id:
                            logging.warning(
                                f"Product {line.product_id.name} not found in HO. Skipping move line for order {entry.name}.")
                            continue

                        product_id = product_id[0]['id']

                        # Handle tax IDs
                        tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                        tax_domain = [('name', '=', f"{line.tax_ids.name}-CREDIT"), ('company_id', '=', company_id[0]['id']), ('nhcl_creadit_note_tax','=',True)]
                        tax_id_url = f"{tax_url_data}?domain={tax_domain}"
                        account_data = requests.get(tax_id_url, headers=headers_source).json()
                        tax_id = account_data.get("data")
                        if not tax_id and company_id:
                            # Fetch parent account if not found
                            parent_tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                            parent_tax_domain = [('name', '=', f"{line.tax_ids.name}-CREDIT"),
                                                 ('company_id', '=', company_id[0]['parent_id'][0]['id']), ('nhcl_creadit_note_tax','=',True)]
                            parent_tax_id_url = f"{parent_tax_url_data}?domain={parent_tax_domain}"
                            parent_tax_data = requests.get(parent_tax_id_url, headers=headers_source).json()
                            tax_id = parent_tax_data.get("data")
                        tax_ids = [(6, 0, [tax['id'] for tax in tax_id])] if tax_id else []

                        # Handle account ID
                        account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        account_domain = [('name', '=', line.account_id.name), ('company_id', '=', company_id[0]['id'])]
                        account_id_url = f"{account_url_data}?domain={account_domain}"
                        account_data = requests.get(account_id_url, headers=headers_source).json()
                        account_id = account_data.get("data")

                        if not account_id and company_id:
                            # Fetch parent account if not found
                            parent_account_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                            parent_account_domain = [('name', '=', line.account_id.name),
                                                     ('company_id', '=', company_id[0]['parent_id'][0]['id'])]
                            parent_account_id_url = f"{parent_account_url_data}?domain={parent_account_domain}"
                            parent_account_data = requests.get(parent_account_id_url, headers=headers_source).json()
                            account_id = parent_account_data.get("data")

                        # Add invoice line to the list
                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "product_id": product_id,
                            "account_id": account_id[0]['id'],
                            "tax_ids": tax_ids if tax_ids else False,
                            "price_unit": line.price_unit,
                            "quantity": line.quantity,
                            # "price_subtotal": line.price_subtotal,
                        }))

                    # Search for existing move
                    account_move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                    account_move_domain = [('name', '=', entry.name), ('company_id', '=', company_id[0]['id'])]
                    account_move_url = f"{account_move_search}?domain={account_move_domain}"
                    account_move_data = requests.get(account_move_url, headers=headers_source).json()
                    move_id = account_move_data.get("data")

                    if not move_id:
                        # If no move found, create a new one
                        move_vals = {
                            "partner_id": partner_id,
                            "name": entry.name,
                            "ref": entry.name,
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "move_type": entry.move_type,
                            "journal_id": account_journal[0]['id'],
                            "amount_total": entry.amount_total,
                            "company_id": company_id[0]['id'],
                            'nhcl_store_je': True,
                            'invoice_line_ids': invoice_lines
                        }
                        print("Sending journal entry data:", move_vals)
                        ho_move_url_data = f"http://{ho_ip}:{ho_port}/api/account.move/create"
                        try:
                            move_data = requests.post(ho_move_url_data, headers=headers_source, json=[move_vals])
                            move_data.raise_for_status()

                            response_json = move_data.json()
                            print('Journal entry creation response:', response_json)

                            if response_json and response_json['success']:
                                entry.nhcl_replication_status = True

                            else:
                                logging.error(f"Failed to create Journal Entry {entry.name}. Response: {response_json}")

                        except requests.exceptions.RequestException as e:
                            logging.error(f"Error while creating journal entry for {entry.name}: {str(e)}")
                            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

            else:
                logging.info("No journal entries found for replication.")

        except Exception as e:
            logging.error(f"General error during journal entry processing: {str(e)}")
            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

        return True

    def get_pos_order_line_data(self):
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

            # 🔍 Directly search relevant POS order lines
            pos_order_lines = self.env['pos.order.line'].search([
                ('vendor_return_disc_price', '>', 0)
            ])

            for pos_line in pos_order_lines:
                order = pos_line.order_id
                pos_reference = order.pos_reference

                order_lines = self.env['pos.order.line'].search([('order_id','=',pos_line.order_id.id)])

                # Check if already present in HO
                store_pos_order_search = f"http://{ho_ip}:{ho_port}/api/store.pos.order.line/search"
                store_pos_order_domain = [('store_pos_ref', '=', pos_reference)]
                ho_pos_order_url = f"{store_pos_order_search}?domain={store_pos_order_domain}"

                try:
                    ho_pos_data = requests.get(ho_pos_order_url, headers=headers_source).json()
                    move_id = ho_pos_data.get("data")
                except Exception as e:
                    ho_id.create_cmr_transaction_server_replication_log("failure", str(e))
                    continue

                for line in order_lines:
                    if line.pack_lot_ids:

                        for lot in line.pack_lot_ids:
                            store_data = {
                                'store_pos_ref': pos_reference,
                                'product_name': line.full_product_name,
                                'lot_name': lot.lot_name,
                                'quantity': line.qty,
                                'amount': line.price_subtotal_incl,
                                'reward_name': pos_line.reward_id.program_id.name,
                                'company_name': pos_line.company_id.name,
                                'vendor_return_disc_price': line.vendor_return_disc_price

                            }

                            if not move_id:
                                ho_store_pos_url_data = f"http://{ho_ip}:{ho_port}/api/store.pos.order.line/create"
                                try:
                                    move_data = requests.post(
                                        ho_store_pos_url_data,
                                        headers=headers_source,
                                        json=[store_data]
                                    )
                                    move_data.raise_for_status()
                                    response_json = move_data.json()
                                    message = response_json.get("message", "No message provided")

                                    if response_json.get('success'):
                                        _logger.info(f"Successfully created Journal Entry {order.name} {message}")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log(
                                            response_json.get('object_name'),
                                            order.id,
                                            200,
                                            'add',
                                            'success',
                                            f"Successfully created Journal Entry {order.name}"
                                        )
                                    else:
                                        _logger.error(f"Failed to create Journal Entry: {message}")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log(
                                            response_json.get('object_name'),
                                            order.id,
                                            200,
                                            'add',
                                            'failure',
                                            message
                                        )
                                except Exception as e:
                                    ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

        except Exception as e:
            ho_id.create_cmr_transaction_server_replication_log("failure", str(e))

        return True

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

            missing_serial_number_lines = self.env['last.scanned.serial.number'].sudo().search([
                ('state', '=', False), ('sent_done', '=', False)
            ])
            if not missing_serial_number_lines:
                _logger.info("No missing serial numbers found.")
                return
            ho_store_pos_url_data = f"http://{ho_ip}:{ho_port}/api/stock.verification.unmatched/create"
            # serial_number_data_list = []
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
                    'store_date': line.create_date.strftime('%Y-%m-%d %H:%M:%S') if line.create_date else False

                }
                # print("serial data", serial_number_data_list)
                # API endpoint to create stock.verification in HO

                try:
                    move_data = requests.post(
                        ho_store_pos_url_data,
                        headers=headers_source,
                        json=serial_number_data_list
                    )
                    response_json = move_data.json()
                    message = response_json.get("message", "No message provided")

                    if response_json.get('success'):
                        _logger.info(f"Successfully created Records {message}")
                        line.sent_done = True
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

        return True


    def store_missing_serial_transaction(self):
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Missing Serial Number Transaction', 'nhcl_status': 'success',
             'nhcl_details_status': 'Function Triggered'})
        self.get_pos_order_line_data()
        self.get_missing_serial_numbers()
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Missing Serial Number Transaction', 'nhcl_status': 'success',
             'nhcl_details_status': 'Function Completed'})

        return True


