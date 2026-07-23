from odoo import models,api,fields,_
import requests
import logging
import traceback
import os
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
from datetime import datetime

class PosOrder(models.Model):
    _inherit = 'pos.order'

    nhcl_status = fields.Boolean('Replication Status', default=False, copy=False)
    warning_message = fields.Char(compute='_compute_warning_message')
    nhcl_integration_count = fields.Selection([('no','No'),('yes','Yes')], default='no', copy=False)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.nhcl_status == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'


    def pos_orders_invoice(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/pos.order/call_action"
                ho_pick_data = requests.post(ho_pick_validate_url, json={}, headers=headers_source)
                ho_pick_data.raise_for_status()
                # Access the JSON content from the response
                ho_pick_vals = ho_pick_data.json()
            except Exception as e:
                ho.create_cmr_transaction_replication_log('POS Journal Entry',self.id,self.name,200,'add',"failure", e)

    def send_pos_order_data_to_ho(self):
        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        if ho_id:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            api_key = ho_id.nhcl_api_key
            headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
            pending_pos_orders = self.env['pos.order'].search([('nhcl_status', '=', False), ('state','=','invoiced'), ('nhcl_integration_count','=','no')])
            for pos_order in pending_pos_orders:
                try:

                    # -------------------- Main Company --------------------
                    main_company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    main_company_domain = [('nhcl_company_bool', '=', True)]
                    main_company_url = f"{main_company_search}?domain={main_company_domain}&fields=['id','name']"
                    main_company_data = requests.get(main_company_url, headers=headers_source).json()
                    main_company_id = main_company_data.get("data")
                    if not main_company_id:
                        msg = f"Main Company not found for Pos Orders {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200, 'add',
                                                                  "failure", msg)
                        pos_order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', pos_order.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}&fields=['id','name']"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Pos Order {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)

                    # -------------------- Session --------------------
                    session_search = f"http://{ho_ip}:{ho_port}/api/pos.session/search"
                    session_domain = [('company_id', '=', company_id[0]['id'])]
                    session_url = f"{session_search}?domain={session_domain}&fields=['id','name']"
                    session_data = requests.get(session_url, headers=headers_source).json()
                    session_id = session_data.get("data")

                    if not session_id:
                        msg = f"Company not found for Session {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                        self.env.cr.commit()

                    # -------------------- Cashier --------------------

                    ho_cashier_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                    ho_cashier_domain = [
                        ('nhcl_id', '=', pos_order.employee_id.nhcl_id),
                        ('company_id', '=', company_id[0]['id'])
                    ]
                    cashier_url = f"{ho_cashier_url}?domain={ho_cashier_domain}&fields=['id','name']"
                    ho_cashier_data = requests.get(cashier_url, headers=headers_source).json()
                    cashier_data = ho_cashier_data.get('data')
                    cashier_id = False
                    if cashier_data:
                        cashier_id = cashier_data[0]['id']
                    if not cashier_data:
                        msg = f"Cashier not found for{pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                        self.env.cr.commit()


                    # Fetch or create the partner in HO
                    partner_url = (f"http://{ho_ip}:{ho_port}/api/res.partner/search?"
                                   f"domain=[('name','=', '{pos_order.partner_id.name}'),('phone','=', '{pos_order.partner_id.phone}')]&fields=['id','name']")
                    partner_data = requests.get(partner_url, headers=headers_source).json()
                    partner = partner_data.get("data", [])
                    new_partner = False
                    if not partner:
                        partner_data = {
                            'name': pos_order.partner_id.name,
                            'phone': pos_order.partner_id.phone,
                        }
                        partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                        partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                json=[partner_data])
                        partner_create_response.raise_for_status()
                        new_partner = partner_create_response.json().get("create_id")

                    partner_id = partner[0]['id'] if partner else new_partner
                    branch_pos_order_search = f"http://{ho_ip}:{ho_port}/api/pos.order/search"
                    branch_pos_order_domain = [('name', '=', pos_order.name), ('company_id', '=', company_id[0]['id'])]
                    branch_pos_order_url = f"{branch_pos_order_search}?domain={branch_pos_order_domain}"
                    branch_pos_order_data = requests.get(branch_pos_order_url, headers=headers_source).json()
                    branch_pos_order = branch_pos_order_data.get("data")
                    if branch_pos_order:
                        pos_order.write({
                            'nhcl_status': True
                        })
                        self.env.cr.commit()
                    pos_line = []

                    for line in pos_order.lines:
                        ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                        if line.product_id.detailed_type == 'service':
                            ho_product_domain = [('name', 'ilike', line.product_id.name)]
                        else:
                            ho_product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                        product_url = f"{ho_product_url}?domain={ho_product_domain}&fields=['id','name']"
                        ho_product_data = requests.get(product_url, headers=headers_source).json()
                        product_data = ho_product_data.get('data')
                        product_id = False
                        if product_data:
                            product_id = product_data[0]["id"]
                        if not product_id:
                            msg = f"Product not found for {line.product_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                            self.env.cr.commit()
                        if line.product_id.detailed_type != 'service':
                            ho_employee_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                            ho_employee_domain = [
                                ('nhcl_id', '=', line.employ_id.nhcl_id),
                                ('company_id', '=', company_id[0]['id'])
                            ]
                            employee_url = f"{ho_employee_url}?domain={ho_employee_domain}&fields=['id','name']"
                            ho_employee_data = requests.get(employee_url, headers=headers_source).json()
                            employee_data = ho_employee_data.get('data')
                            employee_id = False
                            if employee_data:
                                employee_id = employee_data[0]['id']

                            tax_ids = []
                            for tax in line.tax_ids:
                                if tax.company_id.state_id.name != 'Andhra Pradesh':
                                    tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                    tax_domain = [('name', '=', f"{tax.name}-CREDIT"),
                                                  ('company_id', '=', company_id[0]['id']),
                                                  ('nhcl_creadit_note_tax', '=', True)]
                                    tax_id_url = f"{tax_url_data}?domain={tax_domain}&fields=['id','name']"
                                    ho_tax_data = requests.get(tax_id_url, headers=headers_source).json()
                                    tax_data = ho_tax_data.get("data")
                                    tax_id = False
                                    if tax_data:
                                        tax_id = tax_data[0]
                                    if not tax_data:
                                        msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                     pos_order.name, 200, 'add',
                                                                                     "failure",
                                                                                     msg)
                                        self.env.cr.commit()
                                else:
                                        # Fetch parent account if not found
                                    parent_tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                    parent_tax_domain = [('name', '=', f"{tax.name}-CREDIT"),
                                                         ('company_id', '=', main_company_id[0]['id']),
                                                         ('nhcl_creadit_note_tax', '=', True)]
                                    parent_tax_id_url = f"{parent_tax_url_data}?domain={parent_tax_domain}&fields=['id','name']"
                                    parent_tax_data = requests.get(parent_tax_id_url, headers=headers_source).json()
                                    tax_data = parent_tax_data.get("data")
                                    if not tax_data:
                                        msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                     pos_order.name, 200, 'add',
                                                                                     "failure",
                                                                                     msg)
                                        self.env.cr.commit()

                                    tax_id = tax_data[0]
                                tax_ids.append(tax_id['id'])
                            lot_ids = []
                            for lot in line.pack_lot_ids:
                                pack_operation = self.env['pos.pack.operation.lot'].search([('id', '=', lot.id)], limit=1)
                                lot_url_data = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                lot_domain = [('name', '=', pack_operation.lot_name),
                                              ('company_id', '=', company_id[0]['id'])]
                                lot_id_url = f"{lot_url_data}?domain={lot_domain}&fields=['id','name']"
                                lot_data = requests.get(lot_id_url, headers=headers_source).json()

                                if lot_data.get("data"):
                                    lot_ids.append(lot_data["data"][0]['id'])

                                pos_order_line = {
                                    "full_product_name": line.full_product_name,
                                    "product_id": product_id,
                                    "qty": line.qty,
                                    "price_unit": line.price_unit,
                                    "price_subtotal": line.price_subtotal,
                                    "price_subtotal_incl": line.price_subtotal_incl,
                                    "tax_ids": tax_ids if line.tax_ids else False,
                                    "lot_ids": lot_ids if line.pack_lot_ids else False,
                                    "employ_id": employee_id,
                                    "gdiscount": line.gdiscount,
                                    "nhcl_cost_price": line.nhcl_cost_price,
                                    "nhcl_rs_price": line.nhcl_rs_price,
                                    "nhcl_mr_price": line.nhcl_mr_price,
                                    "discount": line.discount,
                                    "total_reward_discount": line.total_reward_discount,
                                    "nhcl_reward_id": line.nhcl_reward_id.display_name,

                                }

                                pos_line.append((0, 0, pos_order_line))

                        # ---------------- Product Line Creation ----------------
                        if line.product_id.detailed_type == 'service':
                            pos_order_line = {
                                "full_product_name": line.full_product_name,
                                "product_id": product_id,
                                "qty": line.qty,
                                "price_unit": line.price_unit,
                                "price_subtotal": line.price_subtotal,
                                "price_subtotal_incl": line.price_subtotal_incl,
                            }
                            pos_line.append((0, 0, pos_order_line))

                    payment_data = []
                    for payment in pos_order.payment_ids:
                        ho_payment_method_url = f"http://{ho_ip}:{ho_port}/api/pos.payment.method/search"
                        ho_payment_method_domain = [('name', '=', payment.payment_method_id.name), ('company_id', '=', company_id[0]['id'])]
                        payment_method_url = f"{ho_payment_method_url}?domain={ho_payment_method_domain}&fields=['id','name']"
                        ho_payment_method_data = requests.get(payment_method_url, headers=headers_source).json()
                        payment_method_data = ho_payment_method_data.get('data')
                        if not payment_method_data:
                            msg = f"Payment Method not found for {payment.payment_method_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                         'add', "failure", msg)
                            self.env.cr.commit()

                        pos_payment_vals = {
                            "payment_date" : payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                            "payment_method_id": payment_method_data[0]['id'],
                            "amount": payment.amount,

                        }
                        payment_data.append((0,0,pos_payment_vals))
                    used_credit_data = []
                    if pos_order.credit_ids:
                        for credit in pos_order.credit_ids:
                            pos_used_credit_vals = {
                                "voucher_number": credit.partner_credit_id.voucher_number,
                                "voucher_amount": credit.amount,

                            }
                            used_credit_data.append((0, 0, pos_used_credit_vals))

                    if not branch_pos_order:
                        pos_order_vals = {
                            "partner_id": partner_id,
                            "name": pos_order.name,
                            "pos_reference": pos_order.pos_reference,
                            "tracking_number": pos_order.tracking_number,
                            "session_id" : session_id[0]['id'],
                            # "session_id" : 8,
                            "amount_tax" : pos_order.amount_tax,
                            "amount_total" : pos_order.amount_total,
                            "amount_paid" : pos_order.amount_paid,
                            "amount_discount" : pos_order.amount_discount,
                            "amount_reward_discount" : pos_order.amount_reward_discount,
                            "amount_return" : pos_order.amount_return,
                            "company_id": company_id[0]['id'],
                            "lines": pos_line,
                            "payment_ids" : payment_data,
                            "voucher_line_ids" : used_credit_data,
                            "state" : "paid",
                            "nhcl_store_je" : True,
                            "date_order": pos_order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                            "employee_id": cashier_id,
                        }
                        branch_pos_order_create_url = f"http://{ho_ip}:{ho_port}/api/pos.order/create"
                        try:
                            branch_pos_data = requests.post(branch_pos_order_create_url, headers=headers_source, json=[pos_order_vals])
                            branch_pos_data.raise_for_status()
                            pos_responsc = branch_pos_data.json()
                            if pos_responsc and pos_responsc['success']:
                                pos_order.write({
                                    'nhcl_status': True
                                })
                                self.env.cr.commit()
                                pos_order_id = pos_responsc.get("create_id")
                                try:
                                    pos_order.pos_orders_invoice()
                                except Exception as req_err:
                                    msg = f"Error creating Invoice for {pos_order.name}: {req_err}"
                                    ho_id.create_cmr_transaction_replication_log('POS Order Invoice',pos_order.id,pos_order.name,200,'add',"failure", msg)
                                    self.env.cr.commit()
                            else:

                                ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", str(pos_responsc))
                                pos_order.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()

                        except requests.exceptions.RequestException as e:
                            ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", str(e))
                            pos_order.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                except Exception as e:
                    msg = f"Unexpected error while processing {pos_order.name}: {e}"
                    ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                    pos_order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue

        return True

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
                ('nhcl_replication_status', '=', False), ('nhcl_integration_count','=','no'), ('journal_id.name', '!=', 'Credit Note Issue'), ('journal_id.type','!=','sale')
            ])

            # if not store_journal_entries:
            #     continue

            for entry in store_journal_entries:
                try:
                    # -------------------- Main Company --------------------
                    main_company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    main_company_domain = [('nhcl_company_bool', '=', True)]
                    main_company_url = f"{main_company_search}?domain={main_company_domain}"
                    main_company_data = requests.get(main_company_url, headers=headers_source).json()
                    main_company_id = main_company_data.get("data")
                    if not main_company_id:
                        msg = f"Main Company not found for Journal Entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry', entry.id, entry.name, 200, 'add',
                                                                  "failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Journal Entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        # -------------------- Journal --------------------
                    if entry.journal_id.company_id.state_id.name != 'Andhra Pradesh':
                        journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        journal_domain = [('name', '=', entry.journal_id.name), ('company_id', '=', company_id[0]['id'])]
                        journal_url = f"{journal_search}?domain={journal_domain}"
                        journal_data = requests.get(journal_url, headers=headers_source).json()
                        account_journal = journal_data.get("data")
                        if not account_journal:
                            msg = f"Journal not found for entry {entry.name}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()

                    # Fallback: try parent company
                    else:
                        parent_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_journal_domain = [
                            ('name', '=', entry.journal_id.name),
                            ('company_id', '=', main_company_id[0]['id'])
                        ]
                        parent_journal_url = f"{parent_journal_search}?domain={parent_journal_domain}"
                        parent_journal_data = requests.get(parent_journal_url, headers=headers_source).json()
                        account_journal = parent_journal_data.get("data")

                        if not account_journal:
                            msg = f"Journal not found for entry {entry.name}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                    # -------------------- Prepare Move Lines --------------------
                    invoice_lines = []
                    for line in entry.line_ids:
                        try:
                            if line.account_id.company_id.state_id.name != 'Andhra Pradesh':
                                account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                account_domain = [
                                    ('name', '=', line.account_id.name),
                                    ('company_id', '=', company_id[0]['id'])
                                ]
                                account_url = f"{account_search}?domain={account_domain}"
                                account_data = requests.get(account_url, headers=headers_source).json()
                                account_id = account_data.get("data")
                                if not account_id:
                                    msg = f"Account not found for line '{line.name}' in entry {entry.name}"
                                    ho.create_cmr_transaction_replication_log('Journal Entry', entry.id, entry.name,
                                                                              200, 'add', "failure", msg)
                                    entry.write({
                                        'nhcl_integration_count': 'yes',
                                    })
                                    self.env.cr.commit()

                            # Fallback: try parent company
                            else:
                                parent_account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                parent_account_domain = [
                                    ('name', '=', line.account_id.name),
                                    ('company_id', '=', main_company_id[0]['id'])
                                ]
                                parent_account_url = f"{parent_account_search}?domain={parent_account_domain}"
                                parent_account_data = requests.get(parent_account_url, headers=headers_source).json()
                                account_id = parent_account_data.get("data")

                            if not account_id:
                                msg = f"Account not found for line '{line.name}' in entry {entry.name}"
                                ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                                entry.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()
                            invoice_lines.append((0, 0, {
                                "name": line.name or '',
                                "account_id": account_id[0]['id'],
                                "debit": line.debit,
                                "credit": line.credit,
                            }))
                        except Exception as line_err:
                            msg = f"Error processing line in entry {entry.name}: {line_err}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                    if not invoice_lines:
                        msg = f"No valid account lines found for entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
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
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        self.env.cr.commit()

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
                            entry.write({
                                'nhcl_replication_status': True
                            })
                            self.env.cr.commit()
                            msg = f"Successfully created Journal Entry {entry.name}"
                            ho.create_cmr_transaction_replication_log(
                                'Journal Entry', entry.id,entry.name, 200, 'add', 'success', msg
                            )
                            self.env.cr.commit()

                        else:
                            msg = f"Failed to create Journal Entry {entry.name}: {response_json.get('message', '')}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            ho.create_cmr_transaction_replication_log(
                                'Journal Entry', entry.id, entry.name, 200, 'add', 'failure', msg
                            )
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()


                    except Exception as api_err:
                        msg = f"API Error creating entry {entry.name}: {api_err}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                except Exception as entry_err:
                    msg = f"Unexpected error while processing {entry.name}: {entry_err}"
                    ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                    entry.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue
        return True

    def get_pos_crediet_note_issue_journal_entry(self):

        ho_id = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ], limit=1)

        try:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            ho_api_key = ho_id.nhcl_api_key

            headers_source = {
                'api-key': f"{ho_api_key}",
                'Content-Type': 'application/json'
            }

            account_journal_id = self.env['account.journal'].search([
                ('name', '=', "Credit Note Issue")
            ], limit=1)

            store_journal_entry = self.env['account.move'].search([
                ('journal_id', '=', account_journal_id.id),
                ('nhcl_replication_status', '=', False), ('nhcl_integration_count','=','no')
            ])

            if not store_journal_entry:
                return True

            for entry in store_journal_entry:
                try:

                    # -------------------- Main Company --------------------
                    main_company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    main_company_domain = [('nhcl_company_bool', '=', True)]
                    main_company_url = f"{main_company_search}?domain={main_company_domain}"
                    main_company_data = requests.get(main_company_url, headers=headers_source).json()
                    main_company_id = main_company_data.get("data")
                    if not main_company_id:
                        msg = f"Main Company not found for Journal Entry {entry.name}"
                        ho_id.create_cmr_transaction_replication_log('Journal Entry', entry.id, entry.name, 200, 'add',
                                                                  "failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # ============================================================
                    # COMPANY SEARCH
                    # ============================================================

                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"

                    company_domain = [
                        ('name', '=', entry.company_id.name)
                    ]

                    company_url = f"{company_search}?domain={company_domain}"

                    company_response = requests.get(
                        company_url,
                        headers=headers_source
                    )

                    company_response.raise_for_status()

                    company_data = company_response.json()

                    company_id = company_data.get("data")

                    if not company_id:
                        error_msg = f"Company not found in HO : {entry.company_id.name}"


                        ho_id.create_cmr_transaction_replication_log(
                            'Credit Note',
                            entry.id,
                            entry.name,
                            200,
                            'add',
                            "failure",
                            error_msg
                        )
                        self.env.cr.commit()

                    # ============================================================
                    # JOURNAL SEARCH
                    # ============================================================
                    if entry.journal_id.company_id.state_id.name != 'Andhra Pradesh':

                        account_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"

                        account_journal_domain = [
                            ('name', '=', 'Credit Note Issue'),
                            ('company_id', '=', company_id[0]['id'])
                        ]

                        account_journal_url = f"{account_journal_search}?domain={account_journal_domain}"

                        account_journal_response = requests.get(
                            account_journal_url,
                            headers=headers_source
                        )

                        account_journal_response.raise_for_status()

                        account_journal_data = account_journal_response.json()

                        account_journal = account_journal_data.get("data")

                    else:
                        parent_company_id = main_company_id[0]['id']

                        parent_account_journal_domain = [
                            ('name', '=', 'Credit Note Issue'),
                            ('company_id', '=', parent_company_id)
                        ]

                        parent_account_journal_url = f"{account_journal_search}?domain={parent_account_journal_domain}"

                        parent_account_journal_response = requests.get(
                            parent_account_journal_url,
                            headers=headers_source
                        )

                        parent_account_journal_response.raise_for_status()

                        parent_account_journal_data = parent_account_journal_response.json()

                        account_journal = parent_account_journal_data.get("data")

                        if not account_journal:
                            error_msg = f"Journal not found in HO for Entry : {entry.name}"


                            ho_id.create_cmr_transaction_replication_log(
                                'Credit Note',
                                entry.id,
                                entry.name,
                                200,
                                'add',
                                "failure",
                                error_msg
                            )
                            self.env.cr.commit()

                    # ============================================================
                    # PARTNER SEARCH
                    # ============================================================

                    partner_domain = [
                        ('name', '=', entry.partner_id.name or ''),
                        ('phone', '=', entry.partner_id.phone or '')
                    ]

                    partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain={partner_domain}"

                    partner_response = requests.get(
                        partner_url,
                        headers=headers_source
                    )

                    partner_response.raise_for_status()

                    partner_data = partner_response.json()

                    partner = partner_data.get("data", [])

                    new_partner = False

                    if not partner:

                        partner_vals = {
                            'name': entry.partner_id.name,
                            'phone': entry.partner_id.phone,
                        }

                        partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"

                        partner_create_response = requests.post(
                            partner_create_url,
                            headers=headers_source,
                            json=[partner_vals]
                        )

                        partner_create_response.raise_for_status()

                        partner_create_json = partner_create_response.json()

                        if not partner_create_json.get('success'):
                            error_msg = f"Partner creation failed : {entry.partner_id.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'Credit Note',
                                entry.id,
                                entry.name,
                                200,
                                'add',
                                "failure",
                                error_msg
                            )
                            self.env.cr.commit()


                        new_partner = partner_create_json.get("create_id")

                    partner_id = partner[0]['id'] if partner else new_partner

                    # ============================================================
                    # INVOICE LINES
                    # ============================================================

                    invoice_lines = []

                    for line in entry.invoice_line_ids:

                        # ========================================================
                        # PRODUCT SEARCH
                        # ========================================================

                        if line.product_id.detailed_type == 'service':

                            product_domain = [
                                ('name', '=', line.product_id.name)
                            ]

                        else:

                            product_domain = [
                                ('nhcl_id', '=', line.product_id.nhcl_id)
                            ]

                        product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"

                        product_response = requests.get(
                            product_url,
                            headers=headers_source
                        )

                        product_response.raise_for_status()

                        product_data = product_response.json()

                        product_id = product_data.get("data", [])

                        if not product_id:
                            error_msg = f"Product not found in HO : {line.product_id.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'Credit Note',
                                entry.id,
                                entry.name,
                                200,
                                'add',
                                "failure",
                                error_msg
                            )
                            self.env.cr.commit()


                        product_id = product_id[0]['id']

                        # ========================================================
                        # TAX SEARCH
                        # ========================================================

                        tax_ids = []

                        if line.tax_ids:
                            if entry.journal_id.company_id.state_id.name != 'Andhra Pradesh':
                                tax_domain = [
                                    ('name', '=', f"{line.tax_ids[0].name}-CREDIT"),
                                    ('company_id', '=', company_id[0]['id']),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]

                                tax_url = f"http://{ho_ip}:{ho_port}/api/account.tax/search?domain={tax_domain}"

                                tax_response = requests.get(
                                    tax_url,
                                    headers=headers_source
                                )

                                tax_response.raise_for_status()

                                tax_data = tax_response.json()

                                tax_id = tax_data.get("data", [])
                                if not tax_id:
                                    error_msg = f"Tax not found : {line.tax_ids[0].name}"
                                    ho_id.create_cmr_transaction_replication_log(
                                        'Credit Note',
                                        entry.id,
                                        entry.name,
                                        200,
                                        'add',
                                        "failure",
                                        error_msg
                                    )
                                    self.env.cr.commit()

                            else:
                                parent_company_id = main_company_id[0]['id']

                                parent_tax_domain = [
                                    ('name', '=', f"{line.tax_ids[0].name}-CREDIT"),
                                    ('company_id', '=', parent_company_id),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]

                                parent_tax_url = f"http://{ho_ip}:{ho_port}/api/account.tax/search?domain={parent_tax_domain}"

                                parent_tax_response = requests.get(
                                    parent_tax_url,
                                    headers=headers_source
                                )

                                parent_tax_response.raise_for_status()

                                parent_tax_data = parent_tax_response.json()

                                tax_id = parent_tax_data.get("data", [])
                                if not tax_id:
                                    error_msg = f"Tax not found : {line.tax_ids[0].name}"
                                    ho_id.create_cmr_transaction_replication_log(
                                        'Credit Note',
                                        entry.id,
                                        entry.name,
                                        200,
                                        'add',
                                        "failure",
                                        error_msg
                                    )
                                    self.env.cr.commit()

                            tax_ids = [(6, 0, [x['id'] for x in tax_id])] if tax_id else []

                        # ========================================================
                        # ACCOUNT SEARCH
                        # ========================================================
                        if line.account_id.company_id.state_id.name != 'Andhra Pradesh':
                            account_domain = [
                                ('name', '=', line.account_id.name),
                                ('company_id', '=', company_id[0]['id'])
                            ]

                            account_url = f"http://{ho_ip}:{ho_port}/api/account.account/search?domain={account_domain}"

                            account_response = requests.get(
                                account_url,
                                headers=headers_source
                            )

                            account_response.raise_for_status()

                            account_data = account_response.json()

                            account_id = account_data.get("data", [])
                            if not account_id:
                                error_msg = f"Account not found : {line.account_id.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'Credit Note',
                                    entry.id,
                                    entry.name,
                                    200,
                                    'add',
                                    "failure",
                                    error_msg
                                )
                                self.env.cr.commit()

                        else:
                            parent_company_id = main_company_id[0]['id']

                            parent_account_domain = [
                                ('name', '=', line.account_id.name),
                                ('company_id', '=', parent_company_id)
                            ]

                            parent_account_url = f"http://{ho_ip}:{ho_port}/api/account.account/search?domain={parent_account_domain}"

                            parent_account_response = requests.get(
                                parent_account_url,
                                headers=headers_source
                            )

                            parent_account_response.raise_for_status()

                            parent_account_data = parent_account_response.json()

                            account_id = parent_account_data.get("data", [])

                            if not account_id:
                                error_msg = f"Account not found : {line.account_id.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'Credit Note',
                                    entry.id,
                                    entry.name,
                                    200,
                                    'add',
                                    "failure",
                                    error_msg
                                )
                                self.env.cr.commit()


                        # ========================================================
                        # APPEND LINE
                        # ========================================================

                        invoice_lines.append((0, 0, {
                            "name": line.name,
                            "product_id": product_id,
                            "account_id": account_id[0]['id'],
                            "tax_ids": tax_ids if tax_ids else False,
                            "price_unit": line.price_unit,
                            "quantity": line.quantity,
                        }))

                    # ============================================================
                    # MOVE SEARCH
                    # ============================================================

                    move_domain = [
                        ('name', '=', entry.name),
                        ('company_id', '=', company_id[0]['id'])
                    ]

                    move_url = f"http://{ho_ip}:{ho_port}/api/account.move/search?domain={move_domain}"

                    move_response = requests.get(
                        move_url,
                        headers=headers_source
                    )

                    move_response.raise_for_status()

                    move_data = move_response.json()

                    move_id = move_data.get("data", [])

                    # ============================================================
                    # CREATE MOVE
                    # ============================================================

                    if not move_id:

                        move_vals = {
                            "partner_id": partner_id,
                            "name": entry.name,
                            "ref": entry.name,
                            "pos_bill_ref": entry.pos_bill_ref,
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "move_type": entry.move_type,
                            "journal_id": account_journal[0]['id'],
                            "amount_total": entry.amount_total,
                            "company_id": company_id[0]['id'],
                            'nhcl_store_je': True,
                            'invoice_line_ids': invoice_lines
                        }

                        create_move_url = f"http://{ho_ip}:{ho_port}/api/account.move/create"

                        move_create_response = requests.post(
                            create_move_url,
                            headers=headers_source,
                            json=[move_vals]
                        )

                        move_create_response.raise_for_status()

                        move_create_json = move_create_response.json()


                        if move_create_json.get('success'):

                            entry.write({
                                'nhcl_replication_status': True
                            })
                            self.env.cr.commit()


                        else:
                            error_msg = f"Journal Entry creation failed : {entry.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'Credit Note',
                                entry.id,
                                entry.name,
                                200,
                                'add',
                                "failure",
                                str(move_create_json)
                            )
                            entry.write({
                                'nhcl_integration_count': 'no',
                            })
                            self.env.cr.commit()

                except Exception as entry_error:
                    ho_id.create_cmr_transaction_replication_log(
                        'Credit Note',
                        entry.id,
                        entry.name,
                        200,
                        'add',
                        "failure",
                        str(entry_error)
                    )
                    entry.write({
                        'nhcl_integration_count': 'no',
                    })
                    self.env.cr.commit()

        except Exception as e:
            ho_id.create_cmr_transaction_replication_log(
                'Credit Note',
                0,
                '/',
                200,
                'add',
                "failure",
                str(e)
            )
        return True

    def merge_pos_delivery_orders(self):
        ho_ids = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_ids:

            session = requests.Session()

            base_url = f"http://{ho.nhcl_terminal_ip}:{ho.nhcl_port_no}/api"

            session.headers.update({
                'api-key': ho.nhcl_api_key,
                'Content-Type': 'application/json'
            })
            picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "pos_order")])
            store_pos_delivery_orders = self.env['stock.picking'].search([
                ('picking_type_id', '=', picking_type_id.id),
                ('nhcl_replication_status', '=', False),
                ('state', '=', 'done'), ('nhcl_integration_count','=','no')
            ])

            for order in store_pos_delivery_orders:
                try:
                    # -------------------------------------------------
                    # COMPANY
                    # -------------------------------------------------
                    company = session.get(
                        f"{base_url}/res.company/search",
                        params={
                            "domain": str([
                                ('name', '=', order.company_id.name)
                            ])
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not company:
                        msg = f"Pos Delivery Order Company Not Found : {order.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    company_id = company[0]['id']

                    # -------------------- POS Order --------------------
                    pos_order = session.get(
                        f"{base_url}/pos.order/search",
                        params={
                            "domain": str([
                                ('name', '=', order.origin),
                                ('company_id', '=', company_id)
                            ]),

                        },
                        timeout=20
                    ).json().get("data", [])

                    if not pos_order:
                        msg = f"POS Order Not Found : {order.origin}"
                        ho.create_cmr_transaction_replication_log(
                            'POS Delivery Order',
                            order.id,
                            order.name,
                            200,
                            'add',
                            "failure",
                            msg
                        )
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    pos_id = pos_order[0]['id']
                    # -------------------------------------------------
                    # PICKING TYPE
                    # -------------------------------------------------
                    picking_type = session.get(
                        f"{base_url}/stock.picking.type/search",
                        params={
                            "domain": str([
                                ('stock_picking_type', '=', order.picking_type_id.stock_picking_type),
                                ('company_id', '=', company_id)
                            ]),"fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not picking_type:
                        msg = f"Pos Delivery Order Picking Type Not Found : {order.picking_type_id.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    # -------------------------------------------------
                    # LOCATIONS
                    # -------------------------------------------------
                    source = session.get(
                        f"{base_url}/stock.location/search",
                        params={
                            "domain": str([
                                ('complete_name', '=', order.location_id.complete_name),
                                ('usage', '=', 'internal'),
                                ('company_id', '=', company_id)
                            ]),
                            "fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    dest = session.get(
                        f"{base_url}/stock.location/search",
                        params={
                            "domain": str([
                                ('complete_name', '=', order.location_dest_id.complete_name),
                                ('usage', '=', 'customer')
                            ]),
                            "fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not source or not dest:
                        msg = f"Pos Delivery Order Locations Not Found : {order.location_idname},{order.location_dest_id.complete_name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    location_id = source[0]['id']
                    dest_id = dest[0]['id']

                    # -------------------------------------------------
                    # CHECK PICKING EXISTS
                    # -------------------------------------------------
                    existing = session.get(
                        f"{base_url}/stock.picking/search",
                        params={
                            "domain": str([
                                ('origin', '=', order.name)
                            ]),"fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if existing:
                        order.write({'nhcl_replication_status' : True,})
                        self.env.cr.commit()

                    # -------------------------------------------------
                    # PRODUCTS SINGLE FETCH
                    # -------------------------------------------------
                    nhcl_ids = list(set(
                        order.move_line_ids_without_package.mapped(
                            'product_id.nhcl_id'
                        )
                    ))

                    products = session.get(
                        f"{base_url}/product.product/search",
                        params={
                            "domain": str([
                                ('nhcl_id', 'in', nhcl_ids)
                            ]),
                            "fields": "['id','nhcl_id']"
                        },
                        timeout=60
                    ).json().get("data", [])

                    product_map = {
                        str(p['nhcl_id']): p['id']
                        for p in products
                    }

                    # -------------------------------------------------
                    # MOVE LINES
                    # -------------------------------------------------
                    move_lines = []

                    for line in order.move_line_ids_without_package:

                        product_id = product_map.get(
                            str(line.product_id.nhcl_id)
                        )

                        if not product_id:
                            msg = f"Pos Delivery Order Product Not Found : {line.product_id.name}"
                            ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                      'add', "failure", msg)
                            order.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()

                        move_lines.append((0, 0, {
                            'product_id': product_id,
                            'quantity': line.quantity,
                            'location_id': location_id,
                            'location_dest_id': dest_id,
                            'lot_name': line.lot_id.name if line.lot_id else False,
                        }))

                    if not move_lines:
                        continue

                    # -------------------------------------------------
                    # SINGLE BULK CREATE
                    # -------------------------------------------------
                    payload = [{
                        'picking_type_id': picking_type[0]['id'],
                        'origin': order.name,
                        'location_id': location_id,
                        'location_dest_id': dest_id,
                        'company_id': company_id,
                        'pos_order_id': pos_id,
                        'move_type': 'direct',
                        'state': 'done',
                        'nhcl_store_delivery': True,
                        'move_line_ids_without_package': move_lines
                    }]

                    response = session.post(
                        f"{base_url}/stock.picking/create",
                        json=payload,
                        timeout=300
                    ).json()

                    if response.get("success"):

                        order.write({'nhcl_replication_status' : True,})
                        self.env.cr.commit()

                        order.validate_orders(
                            deliver_order='pos_order'
                        )
                        msg = f"Pos Delivery Order Created : {order.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order',order.id,order.name,200,'add',"success", msg)


                    else:
                        ho.create_cmr_transaction_replication_log('POS Delivery Order',order.id,order.name,200,'add',"failure", response.get("message"))
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                except Exception as e:
                    ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200, 'add',
                                                              "failure", e)

                    order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
            session.close()
        return True

    def send_pos_orders_ho(self):
        self.env['nhcl.initiated.status.log'].create({
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_job_name': 'POS Order Live Sync',
            'nhcl_status': 'success',
            'nhcl_details_status': 'Function Started'
        })
        self.env.cr.commit()
        self.send_pos_order_data_to_ho()
        #self.get_pos_journal_entry()
        #self.get_pos_crediet_note_issue_journal_entry()
        self.merge_pos_delivery_orders()
        #self.pos_orders_invoice()
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'POS Order Live Sync', 'nhcl_status': 'success',
             'nhcl_details_status': 'Function   Completed'})
        self.env.cr.commit()
        return True

    def each_record_pos_order_data_to_ho(self):
        ho_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
        if ho_id:
            ho_ip = ho_id.nhcl_terminal_ip
            ho_port = ho_id.nhcl_port_no
            api_key = ho_id.nhcl_api_key
            headers_source = {'api-key': f"{api_key}", 'Content_Type': 'application/json'}
            for pos_order in self:
                try:

                    # -------------------- Main Company --------------------
                    main_company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    main_company_domain = [('nhcl_company_bool', '=', True)]
                    main_company_url = f"{main_company_search}?domain={main_company_domain}&fields=['id','name']"
                    main_company_data = requests.get(main_company_url, headers=headers_source).json()
                    main_company_id = main_company_data.get("data")
                    if not main_company_id:
                        msg = f"Main Company not found for Pos Orders {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200, 'add',
                                                                  "failure", msg)
                        pos_order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', pos_order.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}&fields=['id','name']"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Pos Order {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)

                    # -------------------- Session --------------------
                    session_search = f"http://{ho_ip}:{ho_port}/api/pos.session/search"
                    session_domain = [('company_id', '=', company_id[0]['id'])]
                    session_url = f"{session_search}?domain={session_domain}&fields=['id','name']"
                    session_data = requests.get(session_url, headers=headers_source).json()
                    session_id = session_data.get("data")

                    if not session_id:
                        msg = f"Company not found for Session {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                        self.env.cr.commit()

                    # -------------------- Cashier --------------------

                    ho_cashier_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                    ho_cashier_domain = [
                        ('nhcl_id', '=', pos_order.employee_id.nhcl_id),
                        ('company_id', '=', company_id[0]['id'])
                    ]
                    cashier_url = f"{ho_cashier_url}?domain={ho_cashier_domain}&fields=['id','name']"
                    ho_cashier_data = requests.get(cashier_url, headers=headers_source).json()
                    cashier_data = ho_cashier_data.get('data')
                    cashier_id = False
                    if cashier_data:
                        cashier_id = cashier_data[0]['id']
                    if not cashier_data:
                        msg = f"Cashier not found for{pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                        self.env.cr.commit()

                    # Fetch or create the partner in HO
                    partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{pos_order.partner_id.name}'),('phone','=', '{pos_order.partner_id.phone}')]&fields=['id','name']"
                    partner_data = requests.get(partner_url, headers=headers_source).json()
                    partner = partner_data.get("data", [])
                    new_partner = False
                    if not partner:
                        partner_data = {
                            'name': pos_order.partner_id.name,
                            'phone': pos_order.partner_id.phone,
                        }
                        partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                        partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                json=[partner_data])
                        partner_create_response.raise_for_status()
                        new_partner = partner_create_response.json().get("create_id")

                    partner_id = partner[0]['id'] if partner else new_partner
                    branch_pos_order_search = f"http://{ho_ip}:{ho_port}/api/pos.order/search"
                    branch_pos_order_domain = [('name', '=', pos_order.name), ('company_id', '=', company_id[0]['id'])]
                    branch_pos_order_url = f"{branch_pos_order_search}?domain={branch_pos_order_domain}"
                    branch_pos_order_data = requests.get(branch_pos_order_url, headers=headers_source).json()
                    branch_pos_order = branch_pos_order_data.get("data")
                    if branch_pos_order:
                        pos_order.write({
                            'nhcl_status': True
                        })
                        self.env.cr.commit()
                    pos_line = []

                    for line in pos_order.lines:
                        ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                        if line.product_id.detailed_type == 'service':
                            ho_product_domain = [('name', 'ilike', line.product_id.name)]
                        else:
                            ho_product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                        product_url = f"{ho_product_url}?domain={ho_product_domain}&fields=['id','name']"
                        ho_product_data = requests.get(product_url, headers=headers_source).json()
                        product_data = ho_product_data.get('data')
                        product_id = False
                        if product_data:
                            product_id = product_data[0]["id"]
                        if not product_id:
                            msg = f"Product not found for {line.product_id.name}/{pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                            self.env.cr.commit()
                        if line.product_id.detailed_type != 'service':
                            ho_employee_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                            ho_employee_domain = [
                                ('nhcl_id', '=', line.employ_id.nhcl_id),
                                ('company_id', '=', company_id[0]['id'])
                            ]
                            employee_url = f"{ho_employee_url}?domain={ho_employee_domain}&fields=['id','name']"
                            ho_employee_data = requests.get(employee_url, headers=headers_source).json()
                            employee_data = ho_employee_data.get('data')
                            employee_id = False
                            if employee_data:
                                employee_id = employee_data[0]['id']

                            tax_ids = []
                            for tax in line.tax_ids:
                                if tax.company_id.state_id.name != 'Andhra Pradesh':
                                    tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                    tax_domain = [('name', '=', f"{tax.name}-CREDIT"),
                                                  ('company_id', '=', company_id[0]['id']),
                                                  ('nhcl_creadit_note_tax', '=', True)]
                                    tax_id_url = f"{tax_url_data}?domain={tax_domain}&fields=['id','name']"
                                    ho_tax_data = requests.get(tax_id_url, headers=headers_source).json()
                                    tax_data = ho_tax_data.get("data")
                                    tax_id = False
                                    if tax_data:
                                        tax_id = tax_data[0]
                                    if not tax_data:
                                        msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                     pos_order.name, 200, 'add',
                                                                                     "failure",
                                                                                     msg)
                                        self.env.cr.commit()
                                else:
                                        # Fetch parent account if not found
                                    parent_tax_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                    parent_tax_domain = [('name', '=', f"{tax.name}-CREDIT"),
                                                         ('company_id', '=', main_company_id[0]['id']),
                                                         ('nhcl_creadit_note_tax', '=', True)]
                                    parent_tax_id_url = f"{parent_tax_url_data}?domain={parent_tax_domain}&fields=['id','name']"
                                    parent_tax_data = requests.get(parent_tax_id_url, headers=headers_source).json()
                                    tax_data = parent_tax_data.get("data")
                                    if not tax_data:
                                        msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                     pos_order.name, 200, 'add',
                                                                                     "failure",
                                                                                     msg)
                                        self.env.cr.commit()
                                    # if tax_data:
                                    tax_id = tax_data[0]
                                tax_ids.append(tax_id['id'])
                            lot_ids = []
                            for lot in line.pack_lot_ids:
                                pack_operation = self.env['pos.pack.operation.lot'].search([('id', '=', lot.id)], limit=1)
                                lot_url_data = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                lot_domain = [('name', '=', pack_operation.lot_name),
                                              ('company_id', '=', company_id[0]['id'])]
                                lot_id_url = f"{lot_url_data}?domain={lot_domain}&fields=['id','name']"
                                lot_data = requests.get(lot_id_url, headers=headers_source).json()

                                if lot_data.get("data"):
                                    lot_ids.append(lot_data["data"][0]['id'])

                                pos_order_line = {
                                    "full_product_name": line.full_product_name,
                                    "product_id": product_id,
                                    "qty": line.qty,
                                    "price_unit": line.price_unit,
                                    "price_subtotal": line.price_subtotal,
                                    "price_subtotal_incl": line.price_subtotal_incl,
                                    "tax_ids": tax_ids if line.tax_ids else False,
                                    "lot_ids": lot_ids if line.pack_lot_ids else False,
                                    "employ_id": employee_id,
                                    "gdiscount": line.gdiscount,
                                    "nhcl_cost_price": line.nhcl_cost_price,
                                    "nhcl_rs_price": line.nhcl_rs_price,
                                    "nhcl_mr_price": line.nhcl_mr_price,
                                    "discount": line.discount,
                                    "total_reward_discount": line.total_reward_discount,
                                    "nhcl_reward_id": line.nhcl_reward_id.display_name,

                                }

                                pos_line.append((0, 0, pos_order_line))

                        # ---------------- Product Line Creation ----------------
                        if line.product_id.detailed_type == 'service':
                            pos_order_line = {
                                "full_product_name": line.full_product_name,
                                "product_id": product_id,
                                "qty": line.qty,
                                "price_unit": line.price_unit,
                                "price_subtotal": line.price_subtotal,
                                "price_subtotal_incl": line.price_subtotal_incl,
                            }
                            pos_line.append((0, 0, pos_order_line))

                    payment_data = []
                    for payment in pos_order.payment_ids:
                        ho_payment_method_url = f"http://{ho_ip}:{ho_port}/api/pos.payment.method/search"
                        ho_payment_method_domain = [('name', '=', payment.payment_method_id.name), ('company_id', '=', company_id[0]['id'])]
                        payment_method_url = f"{ho_payment_method_url}?domain={ho_payment_method_domain}&fields=['id','name']"
                        ho_payment_method_data = requests.get(payment_method_url, headers=headers_source).json()
                        payment_method_data = ho_payment_method_data.get('data')
                        if not payment_method_data:
                            msg = f"Payment Method not found for {payment.payment_method_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                         'add', "failure", msg)
                            self.env.cr.commit()

                        pos_payment_vals = {
                            "payment_date" : payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                            "payment_method_id": payment_method_data[0]['id'],
                            "amount": payment.amount,

                        }
                        payment_data.append((0,0,pos_payment_vals))
                    used_credit_data = []
                    if pos_order.credit_ids:
                        for credit in pos_order.credit_ids:
                            pos_used_credit_vals = {
                                "voucher_number": credit.partner_credit_id.voucher_number,
                                "voucher_amount": credit.amount,

                            }
                            used_credit_data.append((0, 0, pos_used_credit_vals))

                    if not branch_pos_order:
                        pos_order_vals = {
                            "partner_id": partner_id,
                            "name": pos_order.name,
                            "pos_reference": pos_order.pos_reference,
                            "tracking_number": pos_order.tracking_number,
                            "session_id" : session_id[0]['id'],
                            # "session_id" : 8,
                            "amount_tax" : pos_order.amount_tax,
                            "amount_total" : pos_order.amount_total,
                            "amount_paid" : pos_order.amount_paid,
                            "amount_discount" : pos_order.amount_discount,
                            "amount_reward_discount" : pos_order.amount_reward_discount,
                            "amount_return" : pos_order.amount_return,
                            "company_id": company_id[0]['id'],
                            "lines": pos_line,
                            "payment_ids" : payment_data,
                            "voucher_line_ids" : used_credit_data,
                            "state" : "paid",
                            "nhcl_store_je" : True,
                            "date_order": pos_order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                            "employee_id": cashier_id,
                        }
                        branch_pos_order_create_url = f"http://{ho_ip}:{ho_port}/api/pos.order/create"
                        try:
                            branch_pos_data = requests.post(branch_pos_order_create_url, headers=headers_source, json=[pos_order_vals])
                            branch_pos_data.raise_for_status()
                            pos_responsc = branch_pos_data.json()
                            if pos_responsc and pos_responsc['success']:
                                pos_order.write({
                                    'nhcl_status': True
                                })
                                self.env.cr.commit()
                                pos_order_id = pos_responsc.get("create_id")
                                try:
                                    pos_order.pos_orders_invoice()
                                except Exception as req_err:
                                    msg = f"Error creating Invoice for {pos_order.name}: {req_err}"
                                    ho_id.create_cmr_transaction_replication_log('POS Order Invoice',pos_order.id,pos_order.name,200,'add',"failure", msg)
                                    self.env.cr.commit()
                            else:

                                ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", str(pos_responsc))
                                pos_order.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()

                        except requests.exceptions.RequestException as e:
                            ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", str(e))
                            pos_order.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                except Exception as e:
                    msg = f"Unexpected error while processing {pos_order.name}: {e}"
                    ho_id.create_cmr_transaction_replication_log('POS Order',pos_order.id,pos_order.name,200,'add',"failure", msg)
                    pos_order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue

        return True



class AccountMove(models.Model):
    _inherit = 'account.move'

    warning_message = fields.Char(compute='_compute_warning_message')
    nhcl_integration_count = fields.Selection([('no','No'),('yes','Yes')], default='no', copy=False)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.nhcl_replication_status == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

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
            for entry in self:
                try:
                    # -------------------- Main Company --------------------
                    main_company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    main_company_domain = [('nhcl_company_bool', '=', True)]
                    main_company_url = f"{main_company_search}?domain={main_company_domain}&field=['id', 'name']"
                    main_company_data = requests.get(main_company_url, headers=headers_source).json()
                    main_company_id = main_company_data.get("data")
                    if not main_company_id:
                        msg = f"Main Company not found for Journal Entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry', entry.id, entry.name, 200, 'add',
                                                                  "failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', entry.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}&field=['id', 'name']"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Journal Entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        # -------------------- Journal --------------------
                    if entry.journal_id.company_id.state_id.name != 'Andhra Pradesh':
                        journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        journal_domain = [('name', '=', entry.journal_id.name), ('company_id', '=', company_id[0]['id'])]
                        journal_url = f"{journal_search}?domain={journal_domain}&field=['id', 'name']"
                        journal_data = requests.get(journal_url, headers=headers_source).json()
                        account_journal = journal_data.get("data")
                        if not account_journal:
                            msg = f"Journal not found for entry {entry.name}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()

                    # Fallback: try parent company
                    else:
                        parent_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_journal_domain = [
                            ('name', '=', entry.journal_id.name),
                            ('company_id', '=', main_company_id[0]['id'])
                        ]
                        parent_journal_url = f"{parent_journal_search}?domain={parent_journal_domain}&field=['id', 'name']"
                        parent_journal_data = requests.get(parent_journal_url, headers=headers_source).json()
                        account_journal = parent_journal_data.get("data")

                        if not account_journal:
                            msg = f"Journal not found for entry {entry.name}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                    # -------------------- Prepare Move Lines --------------------
                    invoice_lines = []
                    for line in entry.line_ids:
                        try:
                            if line.account_id.company_id.state_id.name != 'Andhra Pradesh':
                                account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                account_domain = [
                                    ('name', '=', line.account_id.name),
                                    ('company_id', '=', company_id[0]['id'])
                                ]
                                account_url = f"{account_search}?domain={account_domain}&field=['id', 'name']"
                                account_data = requests.get(account_url, headers=headers_source).json()
                                account_id = account_data.get("data")
                                if not account_id:
                                    msg = f"Account not found for line '{line.name}' in entry {entry.name}"
                                    ho.create_cmr_transaction_replication_log('Journal Entry', entry.id, entry.name,
                                                                              200, 'add', "failure", msg)
                                    entry.write({
                                        'nhcl_integration_count': 'yes',
                                    })
                                    self.env.cr.commit()

                            # Fallback: try parent company
                            else:
                                parent_account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                                parent_account_domain = [
                                    ('name', '=', line.account_id.name),
                                    ('company_id', '=', main_company_id[0]['id'])
                                ]
                                parent_account_url = f"{parent_account_search}?domain={parent_account_domain}&field=['id', 'name']"
                                parent_account_data = requests.get(parent_account_url, headers=headers_source).json()
                                account_id = parent_account_data.get("data")

                            if not account_id:
                                msg = f"Account not found for line '{line.name}' in entry {entry.name}"
                                ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                                entry.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()
                            invoice_lines.append((0, 0, {
                                "name": line.name or '',
                                "account_id": account_id[0]['id'],
                                "debit": line.debit,
                                "credit": line.credit,
                            }))
                        except Exception as line_err:
                            msg = f"Error processing line in entry {entry.name}: {line_err}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()
                    if not invoice_lines:
                        msg = f"No valid account lines found for entry {entry.name}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                    # -------------------- Check if already exists --------------------
                    if entry.journal_id.name == "Cash":
                        move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                        move_domain = [('name', '=', entry.name), ('company_id', '=', company_id[0]['id'])]
                        move_url = f"{move_search}?domain={move_domain}&field=['id', 'name']"
                        move_data = requests.get(move_url, headers=headers_source).json()
                        existing_move = move_data.get("data")
                    else:
                        move_search = f"http://{ho_ip}:{ho_port}/api/account.move/search"
                        move_domain = [('ref', '=', entry.ref), ('company_id', '=', company_id[0]['id'])]
                        move_url = f"{move_search}?domain={move_domain}&field=['id', 'name']"
                        move_data = requests.get(move_url, headers=headers_source).json()
                        existing_move = move_data.get("data")
                    if existing_move:
                        msg = f"Journal Entry {entry.name} already exists in HO"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        self.env.cr.commit()

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
                            entry.write({
                                'nhcl_replication_status': True
                            })
                            self.env.cr.commit()
                            msg = f"Successfully created Journal Entry {entry.name}"
                            ho.create_cmr_transaction_replication_log(
                                'Journal Entry', entry.id,entry.name, 200, 'add', 'success', msg
                            )
                            self.env.cr.commit()

                        else:
                            msg = f"Failed to create Journal Entry {entry.name}: {response_json.get('message', '')}"
                            ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                            ho.create_cmr_transaction_replication_log(
                                'Journal Entry', entry.id, entry.name, 200, 'add', 'failure', msg
                            )
                            entry.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()


                    except Exception as api_err:
                        msg = f"API Error creating entry {entry.name}: {api_err}"
                        ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                        entry.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                except Exception as entry_err:
                    msg = f"Unexpected error while processing {entry.name}: {entry_err}"
                    ho.create_cmr_transaction_replication_log('Journal Entry',entry.id,entry.name,200,'add',"failure", msg)
                    entry.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue
        return True


class Picking(models.Model):
    """Inherited stock.picking class to add fields and functions"""
    _inherit = "stock.picking"

    def merge_pos_delivery_orders(self):
        ho_ids = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_ids:

            session = requests.Session()

            base_url = f"http://{ho.nhcl_terminal_ip}:{ho.nhcl_port_no}/api"

            session.headers.update({
                'api-key': ho.nhcl_api_key,
                'Content-Type': 'application/json'
            })
            picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "pos_order")])
            for order in self:
                try:
                    # -------------------------------------------------
                    # COMPANY
                    # -------------------------------------------------
                    company = session.get(
                        f"{base_url}/res.company/search",
                        params={
                            "domain": str([
                                ('name', '=', order.company_id.name)
                            ])
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not company:
                        msg = f"Pos Delivery Order Company Not Found : {order.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    company_id = company[0]['id']

                    # -------------------- POS Order --------------------
                    pos_order = session.get(
                        f"{base_url}/pos.order/search",
                        params={
                            "domain": str([
                                ('name', '=', order.origin),
                                ('company_id', '=', company_id)
                            ]),

                        },
                        timeout=20
                    ).json().get("data", [])

                    if not pos_order:
                        msg = f"POS Order Not Found : {order.origin}"
                        ho.create_cmr_transaction_replication_log(
                            'POS Delivery Order',
                            order.id,
                            order.name,
                            200,
                            'add',
                            "failure",
                            msg
                        )
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    pos_id = pos_order[0]['id']
                    # -------------------------------------------------
                    # PICKING TYPE
                    # -------------------------------------------------
                    picking_type = session.get(
                        f"{base_url}/stock.picking.type/search",
                        params={
                            "domain": str([
                                ('stock_picking_type', '=', order.picking_type_id.stock_picking_type),
                                ('company_id', '=', company_id)
                            ]),"fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not picking_type:
                        msg = f"Pos Delivery Order Picking Type Not Found : {order.picking_type_id.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    # -------------------------------------------------
                    # LOCATIONS
                    # -------------------------------------------------
                    source = session.get(
                        f"{base_url}/stock.location/search",
                        params={
                            "domain": str([
                                ('complete_name', '=', order.location_id.complete_name),
                                ('usage', '=', 'internal'),
                                ('company_id', '=', company_id)
                            ]),
                            "fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    dest = session.get(
                        f"{base_url}/stock.location/search",
                        params={
                            "domain": str([
                                ('complete_name', '=', order.location_dest_id.complete_name),
                                ('usage', '=', 'customer')
                            ]),
                            "fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if not source or not dest:
                        msg = f"Pos Delivery Order Locations Not Found : {order.location_idname},{order.location_dest_id.complete_name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                  'add', "failure", msg)
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                    location_id = source[0]['id']
                    dest_id = dest[0]['id']

                    # -------------------------------------------------
                    # CHECK PICKING EXISTS
                    # -------------------------------------------------
                    existing = session.get(
                        f"{base_url}/stock.picking/search",
                        params={
                            "domain": str([
                                ('origin', '=', order.name)
                            ]),"fields": "['id']"
                        },
                        timeout=20
                    ).json().get("data", [])

                    if existing:
                        order.write({'nhcl_replication_status' : True,})
                        self.env.cr.commit()

                    # -------------------------------------------------
                    # PRODUCTS SINGLE FETCH
                    # -------------------------------------------------
                    nhcl_ids = list(set(
                        order.move_line_ids_without_package.mapped(
                            'product_id.nhcl_id'
                        )
                    ))

                    products = session.get(
                        f"{base_url}/product.product/search",
                        params={
                            "domain": str([
                                ('nhcl_id', 'in', nhcl_ids)
                            ]),
                            "fields": "['id','nhcl_id']"
                        },
                        timeout=60
                    ).json().get("data", [])

                    product_map = {
                        str(p['nhcl_id']): p['id']
                        for p in products
                    }

                    # -------------------------------------------------
                    # MOVE LINES
                    # -------------------------------------------------
                    move_lines = []

                    for line in order.move_line_ids_without_package:

                        product_id = product_map.get(
                            str(line.product_id.nhcl_id)
                        )

                        if not product_id:
                            msg = f"Pos Delivery Order Product Not Found : {line.product_id.name}"
                            ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200,
                                                                      'add', "failure", msg)
                            order.write({
                                'nhcl_integration_count': 'yes',
                            })
                            self.env.cr.commit()

                        move_lines.append((0, 0, {
                            'product_id': product_id,
                            'quantity': line.quantity,
                            'location_id': location_id,
                            'location_dest_id': dest_id,
                            'lot_name': line.lot_id.name if line.lot_id else False,
                        }))

                    if not move_lines:
                        continue

                    # -------------------------------------------------
                    # SINGLE BULK CREATE
                    # -------------------------------------------------
                    payload = [{
                        'picking_type_id': picking_type[0]['id'],
                        'origin': order.name,
                        'location_id': location_id,
                        'location_dest_id': dest_id,
                        'company_id': company_id,
                        'pos_order_id': pos_id,
                        'move_type': 'direct',
                        'state': 'done',
                        'nhcl_store_delivery': True,
                        'move_line_ids_without_package': move_lines
                    }]

                    response = session.post(
                        f"{base_url}/stock.picking/create",
                        json=payload,
                        timeout=300
                    ).json()

                    if response.get("success"):

                        order.write({'nhcl_replication_status' : True,})
                        self.env.cr.commit()

                        order.validate_orders(
                            deliver_order='pos_order'
                        )
                        msg = f"Pos Delivery Order Created : {order.name}"
                        ho.create_cmr_transaction_replication_log('POS Delivery Order',order.id,order.name,200,'add',"success", msg)


                    else:
                        ho.create_cmr_transaction_replication_log('POS Delivery Order',order.id,order.name,200,'add',"failure", response.get("message"))
                        order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()

                except Exception as e:
                    ho.create_cmr_transaction_replication_log('POS Delivery Order', order.id, order.name, 200, 'add',
                                                              "failure", e)

                    order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
            session.close()
        return True


