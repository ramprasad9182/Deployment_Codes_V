from collections import defaultdict

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
            pending_pos_orders = self.env['pos.order'].search([
                ('nhcl_status', '=', False),
                ('state', '=', 'invoiced'),
                ('nhcl_integration_count', '=', 'no'),
                ('date_order', '>=', '2026-07-01 00:00:00'),

            ], limit=500)
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
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add',
                                                                     "failure", msg)
                        pos_order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        break
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', pos_order.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}&fields=['id','name']"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Pos Order {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        break
                    # -------------------- Session --------------------
                    session_search = f"http://{ho_ip}:{ho_port}/api/pos.session/search"
                    session_domain = [('company_id', '=', company_id[0]['id'])]
                    session_url = f"{session_search}?domain={session_domain}&fields=['id','name']"
                    session_data = requests.get(session_url, headers=headers_source).json()
                    session_id = session_data.get("data")

                    if not session_id:
                        msg = f"Company not found for Session {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        self.env.cr.commit()
                        break

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
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        self.env.cr.commit()
                        break

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
                    branch_pos_order_domain = [('name', '=', pos_order.name),
                                               ('pos_reference', '=', pos_order.pos_reference),
                                               ('company_id', '=', company_id[0]['id'])]
                    branch_pos_order_url = f"{branch_pos_order_search}?domain={branch_pos_order_domain}&fields=['id','name','pos_reference']"
                    branch_pos_order_data = requests.get(branch_pos_order_url, headers=headers_source).json()
                    branch_pos_order = branch_pos_order_data.get("data")
                    if branch_pos_order:
                        pos_order.write({
                            'nhcl_status': True
                        })
                        self.env.cr.commit()
                    skip_creation = False
                    pos_line = []

                    for line in pos_order.lines:

                        # ---------------- Product ----------------
                        ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"

                        if line.product_id.detailed_type == 'service':
                            ho_product_domain = [('name', 'ilike', line.product_id.name)]
                        else:
                            ho_product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]

                        product_url = f"{ho_product_url}?domain={ho_product_domain}&fields=['id','name']"
                        ho_product_data = requests.get(product_url, headers=headers_source).json()

                        product_data = ho_product_data.get("data")
                        product_id = product_data[0]["id"] if product_data else False

                        if not product_id:
                            msg = f"Product not found for {line.product_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'POS Order', pos_order.id, pos_order.name,
                                200, 'add', "failure", msg
                            )
                            self.env.cr.commit()
                            skip_creation = True
                            break

                        # ---------------- Service Product ----------------

                        if line.product_id.detailed_type == 'service':
                            pos_line.append((0, 0, {
                                "full_product_name": line.full_product_name,
                                "product_id": product_id,
                                "qty": line.qty,
                                "price_unit": line.price_unit,
                                "price_subtotal": line.price_subtotal,
                                "price_subtotal_incl": line.price_subtotal_incl,
                            }))
                            continue

                        # ---------------- Employee ----------------

                        ho_employee_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                        ho_employee_domain = [
                            ('nhcl_id', '=', line.employ_id.nhcl_id),
                            ('company_id', '=', company_id[0]['id'])
                        ]

                        employee_url = f"{ho_employee_url}?domain={ho_employee_domain}&fields=['id','name']"
                        ho_employee_data = requests.get(employee_url, headers=headers_source).json()

                        employee_data = ho_employee_data.get("data")
                        employee_id = employee_data[0]["id"] if employee_data else False

                        if not employee_id:
                            msg = f"Employee not found for {line.employ_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'POS Order', pos_order.id, pos_order.name,
                                200, 'add', "failure", msg
                            )
                            self.env.cr.commit()
                            skip_creation = True
                            break

                        # ---------------- Taxes ----------------

                        tax_ids = []

                        for tax in line.tax_ids:

                            if tax.company_id.state_id.name != 'Andhra Pradesh':
                                tax_domain = [
                                    ('name', '=', f"{tax.name}-CREDIT"),
                                    ('company_id', '=', company_id[0]['id']),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]
                            else:
                                tax_domain = [
                                    ('name', '=', f"{tax.name}-CREDIT"),
                                    ('company_id', '=', main_company_id[0]['id']),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]

                            tax_url = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                            tax_id_url = f"{tax_url}?domain={tax_domain}&fields=['id','name']"

                            tax_response = requests.get(
                                tax_id_url,
                                headers=headers_source
                            ).json()

                            tax_data = tax_response.get("data")

                            if not tax_data:
                                msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'POS Order', pos_order.id, pos_order.name,
                                    200, 'add', "failure", msg
                                )
                                self.env.cr.commit()
                                skip_creation = True
                                break

                            tax_ids.append(tax_data[0]["id"])

                        if skip_creation:
                            break

                        # ---------------- Lots ----------------

                        lot_ids = []

                        for lot in line.pack_lot_ids:

                            pack_operation = self.env['pos.pack.operation.lot'].browse(lot.id)

                            lot_domain = [
                                ('name', '=', pack_operation.lot_name),
                                ('company_id', '=', company_id[0]['id'])
                            ]

                            lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                            lot_id_url = f"{lot_url}?domain={lot_domain}&fields=['id','name']"

                            lot_response = requests.get(
                                lot_id_url,
                                headers=headers_source
                            ).json()

                            lot_data = lot_response.get("data")

                            if not lot_data:
                                msg = f"Lot not found for {pack_operation.lot_name} In {pos_order.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'POS Order', pos_order.id, pos_order.name,
                                    200, 'add', "failure", msg
                                )
                                self.env.cr.commit()
                                skip_creation = True
                                break

                            lot_ids.append(lot_data[0]["id"])

                        if skip_creation:
                            break

                        # ---------------- POS Line ----------------

                        pos_order_line = {
                            "full_product_name": line.full_product_name,
                            "product_id": product_id,
                            "qty": line.qty,
                            "price_unit": line.price_unit,
                            "price_subtotal": line.price_subtotal,
                            "price_subtotal_incl": line.price_subtotal_incl,
                            "tax_ids": tax_ids if tax_ids else False,
                            "lot_ids": lot_ids if lot_ids else False,
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

                    # Skip creating POS Order
                    if skip_creation:
                        continue

                    payment_data = []
                    for payment in pos_order.payment_ids:
                        ho_payment_method_url = f"http://{ho_ip}:{ho_port}/api/pos.payment.method/search"
                        ho_payment_method_domain = [('name', '=', payment.payment_method_id.name),
                                                    ('company_id', '=', company_id[0]['id'])]
                        payment_method_url = f"{ho_payment_method_url}?domain={ho_payment_method_domain}&fields=['id','name']"
                        ho_payment_method_data = requests.get(payment_method_url, headers=headers_source).json()
                        payment_method_data = ho_payment_method_data.get('data')
                        if not payment_method_data:
                            msg = f"Payment Method not found for {payment.payment_method_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                         'add', "failure", msg)
                            self.env.cr.commit()
                            break

                        pos_payment_vals = {
                            "payment_date": payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                            "payment_method_id": payment_method_data[0]['id'],
                            "amount": payment.amount,

                        }
                        payment_data.append((0, 0, pos_payment_vals))
                    used_credit_data = []
                    if pos_order.credit_ids:
                        for credit in pos_order.credit_ids:
                            pos_used_credit_vals = {
                                "voucher_number": credit.partner_credit_id.voucher_number,
                                "voucher_amount": credit.amount,

                            }
                            used_credit_data.append((0, 0, pos_used_credit_vals))

                    if not branch_pos_order:
                        if pos_line and payment_data:
                            pos_order_vals = {
                                "partner_id": partner_id,
                                "name": pos_order.name,
                                "pos_reference": pos_order.pos_reference,
                                "tracking_number": pos_order.tracking_number,
                                "session_id": session_id[0]['id'],
                                # "session_id" : 8,
                                "amount_tax": pos_order.amount_tax,
                                "amount_total": pos_order.amount_total,
                                "amount_paid": pos_order.amount_paid,
                                "amount_discount": pos_order.amount_discount,
                                "amount_reward_discount": pos_order.amount_reward_discount,
                                "amount_return": pos_order.amount_return,
                                "company_id": company_id[0]['id'],
                                "lines": pos_line,
                                "payment_ids": payment_data,
                                "voucher_line_ids": used_credit_data,
                                "state": "paid",
                                "nhcl_store_je": True,
                                "date_order": pos_order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                                "employee_id": cashier_id,
                            }
                            branch_pos_order_create_url = f"http://{ho_ip}:{ho_port}/api/pos.order/create"
                            try:
                                branch_pos_data = requests.post(branch_pos_order_create_url, headers=headers_source,
                                                                json=[pos_order_vals])
                                branch_pos_data.raise_for_status()
                                pos_responsc = branch_pos_data.json()
                                if pos_responsc and pos_responsc['success']:
                                    pos_order.write({
                                        'nhcl_status': True
                                    })
                                    self.env.cr.commit()

                                else:

                                    ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                 pos_order.name, 200, 'add', "failure",
                                                                                 str(pos_responsc))
                                    pos_order.write({
                                        'nhcl_integration_count': 'yes',
                                    })
                                    self.env.cr.commit()

                            except requests.exceptions.RequestException as e:
                                ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name,
                                                                             200, 'add', "failure", str(e))
                                pos_order.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()
                except Exception as e:
                    msg = f"Unexpected error while processing {pos_order.name}: {e}"
                    ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200, 'add',
                                                                 "failure", msg)
                    pos_order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue

        return True

    def get_pos_journal_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_id:

            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            ho_api_key = ho.nhcl_api_key

            headers_source = {
                'api-key': ho_api_key,
                'Content-Type': 'application/json'
            }

            entries = self.env['account.move'].search([
                ('nhcl_replication_status', '=', False),
                ('type', 'in', ['bank', 'cash']),
                ('date', '>=', '2026-07-01'),
            ], order='date,journal_id')

            if not entries:
                continue

            # ---------------- Group By Company + Date + Journal ----------------
            try:
                groups = defaultdict(list)

                for move in entries:
                    key = (
                        move.company_id.id,
                        move.date,
                        move.journal_id.id
                    )
                    groups[key].append(move)
                # ---------------- Process Every Group ----------------

                for (company_id, move_date, journal_id), moves in groups.items():
                    consolidated = {}

                    # ------------ Consolidate Lines ------------

                    for move in moves:

                        for line in move.line_ids:

                            acc = line.account_id.id

                            if acc not in consolidated:
                                consolidated[acc] = {
                                    'account': line.account_id,
                                    'debit': 0.0,
                                    'credit': 0.0,
                                }

                            consolidated[acc]['debit'] += line.debit
                            consolidated[acc]['credit'] += line.credit

                    # ------------ Prepare Invoice Lines ------------

                    invoice_lines = []
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', move.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    company = False
                    if company_id:
                        company = company_id[0]['id']

                    if not company_id:
                        msg = f"Company not found for Journal Entry {move.name}"
                        ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                     'add', "failure", msg)

                    journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    journal_domain = [('name', '=', move.journal_id.name), ('company_id', '=', company)]
                    journal_url = f"{journal_search}?domain={journal_domain}"
                    journal_data = requests.get(journal_url, headers=headers_source).json()
                    account_journal = journal_data.get("data")

                    if not account_journal:
                        msg = f"Journal not found for Journal Entry {move.name}"
                        ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                     'add', "failure", msg)

                    # Fallback: try parent company
                    if not account_journal and company_id and company_id[0].get('parent_id'):
                        parent_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_journal_domain = [
                            ('name', '=', move.journal_id.name),
                            ('company_id.name', '=', company_id[0]['parent_id'][0]['name'])
                        ]
                        parent_journal_url = f"{parent_journal_search}?domain={parent_journal_domain}"
                        parent_journal_data = requests.get(parent_journal_url, headers=headers_source).json()
                        account_journal = parent_journal_data.get("data")
                        if not account_journal:
                            msg = f"Journal not found for Journal Entry {move.name}"
                            ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                         'add', "failure", msg)

                    account_map = {}

                    for vals in consolidated.values():

                        account_name = vals['account'].name

                        if account_name in account_map:
                            continue

                        account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"

                        account_domain = [
                            ('name', '=', account_name),
                            ('company_id', '=', company_id[0]['id'])
                        ]

                        account_url = f"{account_search}?domain={account_domain}"

                        account_data = requests.get(account_url, headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id:
                            msg = f"Account not found for Journal Entry {move.name}"
                            ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                         'add', "failure", msg)

                        # Parent company fallback
                        if not account_id and company_id and company_id[0].get('parent_id'):
                            parent_domain = [
                                ('name', '=', account_name),
                                ('company_id', '=', company_id[0]['parent_id'][0]['id'])
                            ]

                            parent_url = f"{account_search}?domain={parent_domain}"

                            parent_data = requests.get(parent_url, headers=headers_source).json()
                            account_id = parent_data.get("data")
                            if not account_id:
                                msg = f"Account not found for Journal Entry {move.name}"
                                ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                             'add', "failure", msg)

                        if account_id:
                            account_map[account_name] = account_id[0]['id']

                    for vals in consolidated.values():
                        ho_account_id = account_map.get(vals['account'].name)

                        # if not ho_account_id:
                        #     continue

                        invoice_lines.append((0, 0, {
                            'account_id': ho_account_id,
                            'debit': round(vals['debit'], 2),
                            'credit': round(vals['credit'], 2),
                        }))

                    move_vals = {
                        'date': move_date.strftime('%Y-%m-%d'),
                        'move_type': 'entry',
                        'journal_id': account_journal[0]['id'],
                        'company_id': company,
                        'line_ids': invoice_lines,
                        'nhcl_store_je': True,
                    }

                    ho_move_url = f"http://{ho_ip}:{ho_port}/api/account.move/create"

                    response = requests.post(
                        ho_move_url,
                        headers=headers_source,
                        json=[move_vals]
                    )

                    response.raise_for_status()

                    result = response.json()

                    if result.get("success"):
                        for move in moves:
                            move.write({
                                'nhcl_replication_status': True
                            })
                            self.env.cr.commit()
                    else:
                        for move in moves:
                            ho.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200, 'add',
                                                                      "failure", e)


            except Exception as e:
                ho.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200, 'add',
                                                          "failure", e)

    def get_pos_customer_invoices_entry(self):
        ho_id = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_id:

            ho_ip = ho.nhcl_terminal_ip
            ho_port = ho.nhcl_port_no
            ho_api_key = ho.nhcl_api_key

            headers_source = {
                'api-key': ho_api_key,
                'Content-Type': 'application/json'
            }

            # entries = self.env['account.move'].search([
            #     ('nhcl_replication_status', '=', False),
            #     ('journal_id.name', 'not in', ['Customer Invoices', 'Credit Note Issue'])
            # ], order='date,journal_id')

            entries = self.env['account.move'].search([
                ('nhcl_replication_status', '=', False),
                ('type', '=', 'sale'),
                ('date', '>=', '2026-07-01'),
            ], order='date,journal_id')

            if not entries:
                continue

            # ---------------- Group By Company + Date + Journal ----------------
            try:
                groups = defaultdict(list)

                for move in entries:
                    key = (
                        move.company_id.id,
                        move.date,
                        move.journal_id.id
                    )
                    groups[key].append(move)

                # ---------------- Process Every Group ----------------

                for (company_id, move_date, journal_id), moves in groups.items():

                    first_move = moves[0]

                    # -------------------------------------------------
                    # Company Search
                    # -------------------------------------------------
                    # Use your existing Company Search logic here
                    ho_company_id = company_id

                    # -------------------------------------------------
                    # Journal Search
                    # -------------------------------------------------
                    # Use your existing Journal Search logic here
                    ho_journal_id = journal_id

                    consolidated = {}

                    for move in moves:
                        for line in move.line_ids:

                            label = (line.name or '').strip()

                            # Only bifurcate CGST/SGST labels
                            if 'CGST' in label.upper() or 'SGST' in label.upper():
                                key = (line.account_id.id, label)
                            else:
                                # Consolidate other accounts normally
                                key = (line.account_id.id,)

                            if key not in consolidated:
                                consolidated[key] = {
                                    'account': line.account_id,
                                    'label': label,
                                    'debit': 0.0,
                                    'credit': 0.0,
                                }

                            consolidated[key]['debit'] += line.debit
                            consolidated[key]['credit'] += line.credit

                    # ------------ Prepare Invoice Lines ------------

                    invoice_lines = []
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', move.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")
                    company = False
                    if company_id:
                        company = company_id[0]['id']

                    if not company_id:
                        msg = f"Company not found for Journal Entry {move.name}"
                        ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                     'add', "failure", msg)

                    journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                    journal_domain = [('name', '=', move.journal_id.name), ('company_id', '=', company)]
                    journal_url = f"{journal_search}?domain={journal_domain}"
                    journal_data = requests.get(journal_url, headers=headers_source).json()
                    account_journal = journal_data.get("data")
                    if not account_journal:
                        msg = f"Journal not found for Journal Entry {move.name}"
                        ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                     'add', "failure", msg)

                    # Fallback: try parent company
                    if not account_journal and company_id and company_id[0].get('parent_id'):
                        parent_journal_search = f"http://{ho_ip}:{ho_port}/api/account.journal/search"
                        parent_journal_domain = [
                            ('name', '=', move.journal_id.name),
                            ('company_id.name', '=', company_id[0]['parent_id'][0]['name'])
                        ]
                        parent_journal_url = f"{parent_journal_search}?domain={parent_journal_domain}"
                        parent_journal_data = requests.get(parent_journal_url, headers=headers_source).json()
                        account_journal = parent_journal_data.get("data")
                        if not account_journal:
                            msg = f"Journal not found for Journal Entry {move.name}"
                            ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                         'add', "failure", msg)

                    account_map = {}

                    for vals in consolidated.values():

                        account_name = vals['account'].name

                        if account_name in account_map:
                            continue

                        account_search = f"http://{ho_ip}:{ho_port}/api/account.account/search"

                        account_domain = [
                            ('name', '=', account_name),
                            ('company_id', '=', company_id[0]['id'])
                        ]

                        account_url = f"{account_search}?domain={account_domain}"

                        account_data = requests.get(account_url, headers=headers_source).json()
                        account_id = account_data.get("data")
                        if not account_id:
                            msg = f"Account not found for Journal Entry {move.name}"
                            ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                         'add', "failure", msg)

                        # Parent company fallback
                        if not account_id and company_id and company_id[0].get('parent_id'):
                            parent_domain = [
                                ('name', '=', account_name),
                                ('company_id', '=', company_id[0]['parent_id'][0]['id'])
                            ]

                            parent_url = f"{account_search}?domain={parent_domain}"

                            parent_data = requests.get(parent_url, headers=headers_source).json()
                            account_id = parent_data.get("data")
                            if not account_id:
                                msg = f"Account not found for Journal Entry {move.name}"
                                ho_id.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200,
                                                                             'add', "failure", msg)

                        if account_id:
                            account_map[account_name] = account_id[0]['id']

                    for vals in consolidated.values():
                        ho_account_id = account_map.get(vals['account'].name)

                        if not ho_account_id:
                            _logger.warning("Account not found for %s", vals['account'].name)
                            msg = "Account not found for %s", vals['account'].name
                            ho.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200, 'add',
                                                                      "failure", msg)
                            continue

                        label = (vals.get('label') or '').upper()

                        line_vals = {
                            'account_id': ho_account_id,
                            'debit': round(vals['debit'], 2),
                            'credit': round(vals['credit'], 2),
                        }

                        if 'CGST' in label or 'SGST' in label:
                            line_vals['name'] = vals['label']

                        invoice_lines.append((0, 0, line_vals))

                    move_vals = {
                        'date': move_date.strftime('%Y-%m-%d'),
                        'move_type': 'entry',
                        'journal_id': account_journal[0]['id'],
                        'company_id': company,
                        'line_ids': invoice_lines,
                        'nhcl_store_je': True,
                    }

                    ho_move_url = f"http://{ho_ip}:{ho_port}/api/account.move/create"

                    response = requests.post(
                        ho_move_url,
                        headers=headers_source,
                        json=[move_vals]
                    )

                    response.raise_for_status()

                    result = response.json()

                    if result.get("success"):
                        for move in moves:
                            move.write({
                                'nhcl_replication_status': True
                            })
                            self.env.cr.commit()
                    else:
                        for move in moves:
                            ho.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200, 'add',
                                                                      "failure", e)

            except Exception as e:
                ho.create_cmr_transaction_replication_log('Journal Entry', move.id, move.name, 200, 'add',
                                                          "failure", e)

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
            # store_pos_delivery_orders = self.env['stock.picking'].search([
            #     ('picking_type_id', '=', picking_type_id.id),
            #     ('nhcl_replication_status', '=', False),
            #     ('state', '=', 'done'), ('nhcl_integration_count','=','no')
            # ])
            store_pos_delivery_orders = self.env['stock.picking'].search([
                ('picking_type_id', '=', picking_type_id.id),
                ('nhcl_replication_status', '=', False),
                ('state', '=', 'done'),
                ('nhcl_integration_count', '=', 'no'),
                ('scheduled_date', '>=', '2026-07-01 00:00:00'),
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
                                # ('complete_name', '=', order.location_id.complete_name),
                                ('usage', '=', 'internal'),
                                ('company_id', '=', company_id),
                                ('cmr_location_type', '=', order.location_id.cmr_location_type)

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

                    if move_lines:

                    # -------------------------------------------------
                    # SINGLE BULK CREATE
                    # -------------------------------------------------
                        payload = [{
                            'picking_type_id': picking_type[0]['id'],
                            'origin': order.name,
                            'date_done': order.date_done.strftime('%Y-%m-%d %H:%M:%S'),
                            'scheduled_date': order.scheduled_date.strftime('%Y-%m-%d %H:%M:%S'),
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

    def store_pos_delivery_orders(self):
        # =========================================================================
        # HELPER FUNCTIONS TO SAFELY EXTRACT IDS & VALUES FROM API RESPONSES
        # =========================================================================
        def extract_id(val):
            if isinstance(val, list) and val:
                val = val[0]
            if isinstance(val, dict):
                return val.get("id")
            return val

        def extract_val(val):
            if isinstance(val, list) and val:
                val = val[0]
            if isinstance(val, dict):
                return val.get("value") or val.get("name") or val.get("id")
            return val

        ho_id = self.env["nhcl.ho.store.master"].search(
            [("nhcl_store_type", "=", "ho"), ("nhcl_active", "=", True)], limit=1
        )

        if not ho_id:
            return True

        def log_order_failure(order, msg, mark_failed=False):
            try:
                ho_id.create_cmr_transaction_replication_log(
                    "POS Delivery Order",
                    order.id,
                    order.name,
                    200,
                    "add",
                    "failure",
                    str(msg)[:500],  # Limit message length for DB safety
                )
                if mark_failed:
                    order.write({"nhcl_integration_count": "yes"})
            except Exception:
                pass

        ho_ip = ho_id.nhcl_terminal_ip
        ho_port = ho_id.nhcl_port_no
        api_key = ho_id.nhcl_api_key
        base_url = f"http://{ho_ip}:{ho_port}/api"

        session = requests.Session()
        session.headers.update(
            {"api-key": f"{api_key}", "Content-Type": "application/json"}
        )

        picking_type_id = self.env["stock.picking.type"].search(
            [("stock_picking_type", "=", "pos_order")], limit=1
        )

        store_pos_delivery_orders = self.env['stock.picking'].search([
            ('picking_type_id', '=', picking_type_id.id),
            ('nhcl_replication_status', '=', False),
            ('state', '=', 'done'),
            ('nhcl_integration_count', '=', 'no'),
            ('scheduled_date', '>=', '2026-08-01 00:00:00'),
        ], limit=200)

        if not store_pos_delivery_orders:
            session.close()
            return True

        # =========================================================================
        # 1. BULK PRE-FETCHING & IN-MEMORY INDEXING
        # =========================================================================

        try:
            # Pre-fetch Main Company
            main_comp_res = session.get(
                f"{base_url}/res.company/search",
                params={
                    "domain": "[('nhcl_company_bool','=',True)]",
                    "fields": "['id','name']",
                },
                timeout=120,
            ).json()

            main_company_data = main_comp_res.get("data", [])
            if not main_company_data:
                for order in store_pos_delivery_orders:
                    log_order_failure(order, f"Pos Delivery Order Main Company Not Found : {order.name}",
                                      mark_failed=True)
                session.close()
                return True

            main_company_id = extract_id(main_company_data[0].get("id"))

            # Pre-fetch POS Orders & Fast-Index Lines into Hash Maps
            order_origins = list(filter(None, store_pos_delivery_orders.mapped("origin")))
            pos_orders = self.env["pos.order"].search([("name", "in", order_origins)])
            pos_order_map = {p.name: p for p in pos_orders}

            # Index POS Lines
            pos_line_by_lot = {}
            pos_line_by_prod = {}

            for line in pos_orders.lines:
                key_prod = (line.order_id.id, line.product_id.id)
                if key_prod not in pos_line_by_prod:
                    pos_line_by_prod[key_prod] = line

                for lot in line.pack_lot_ids:
                    if lot.lot_name:
                        pos_line_by_lot[(line.order_id.id, line.product_id.id, lot.lot_name)] = line

            # PARTNER LOOKUP & BULK AUTO-CREATION (By Name & Phone)
            partner_map = {}
            local_partners = pos_orders.mapped("partner_id").filtered(lambda p: p.name)
            partner_names = list(set(local_partners.mapped("name")))
            partner_phones = list(filter(None, set(local_partners.mapped("phone"))))

            if partner_names:
                # Domain to match name OR phone
                partner_domain = ["|", ("name", "in", partner_names),
                                  ("phone", "in", partner_phones)] if partner_phones else [
                    ("name", "in", partner_names)]

                partner_res = session.get(
                    f"{base_url}/res.partner/search",
                    params={
                        "domain": str(partner_domain),
                        "fields": "['id','name','phone']",
                    },
                    timeout=120,
                ).json()

                for p in partner_res.get("data", []):
                    p_name = extract_val(p.get("name"))
                    p_phone = extract_val(p.get("phone")) or False
                    p_id = extract_id(p.get("id"))
                    if p_id:
                        if p_name and p_phone:
                            partner_map[(p_name, p_phone)] = p_id
                        if p_name:
                            partner_map[p_name] = p_id
                        if p_phone:
                            partner_map[p_phone] = p_id

                missing_partners_payload = []
                missing_keys = []
                for partner in local_partners:
                    p_name = partner.name
                    p_phone = partner.phone or False
                    key = (p_name, p_phone)

                    # Check if partner exists by (name, phone), name, or phone
                    is_known = key in partner_map or p_name in partner_map or (p_phone and p_phone in partner_map)

                    if not is_known and key not in missing_keys:
                        missing_partners_payload.append({"name": p_name, "phone": p_phone})
                        missing_keys.append(key)

                if missing_partners_payload:
                    create_res = session.post(
                        f"{base_url}/res.partner/create",
                        json=missing_partners_payload,
                        timeout=300,
                    ).json()

                    c_ids = create_res.get("create_id") or create_res.get("ids") or create_res.get("data")
                    if isinstance(c_ids, int):
                        c_ids = [c_ids]
                    if isinstance(c_ids, list):
                        for idx, c_id in enumerate(c_ids):
                            if idx < len(missing_keys):
                                ho_p_id = extract_id(c_id)
                                key = missing_keys[idx]
                                partner_map[key] = ho_p_id
                                partner_map[key[0]] = ho_p_id
                                if key[1]:
                                    partner_map[key[1]] = ho_p_id

            # Pre-fetch Store Companies
            company_names = list(set(store_pos_delivery_orders.mapped("company_id.name")))
            company_res = session.get(
                f"{base_url}/res.company/search",
                params={
                    "domain": str([("name", "in", company_names)]),
                    "fields": "['id','name']",
                },
                timeout=120,
            ).json()
            company_map = {
                extract_val(c.get("name")): extract_id(c.get("id"))
                for c in company_res.get("data", [])
                if extract_val(c.get("name")) and extract_id(c.get("id"))
            }
            company_ids = list(company_map.values())

            # Pre-check Existing Pickings in HO
            order_names = store_pos_delivery_orders.mapped("name")
            existing_res = session.get(
                f"{base_url}/stock.picking/search",
                params={
                    "domain": str([("origin", "in", order_names)]),
                    "fields": "['id','origin']",
                },
                timeout=120,
            ).json()
            existing_origins = {
                p["origin"] for p in existing_res.get("data", []) if p.get("origin")
            }

            # Pre-fetch Picking Types
            picking_type_codes = list(set(store_pos_delivery_orders.mapped("picking_type_id.stock_picking_type")))
            picking_type_map = {}
            if company_ids and picking_type_codes:
                pt_res = session.get(
                    f"{base_url}/stock.picking.type/search",
                    params={
                        "domain": str([
                            ("stock_picking_type", "in", picking_type_codes),
                            ("company_id", "in", company_ids),
                        ]),
                        "fields": "['id','stock_picking_type','company_id']",
                    },
                    timeout=120,
                ).json()
                for pt in pt_res.get("data", []):
                    pt_code = extract_val(pt.get("stock_picking_type"))
                    comp_id = extract_id(pt.get("company_id"))
                    pt_id = extract_id(pt.get("id"))
                    if pt_code and comp_id and pt_id:
                        picking_type_map[(pt_code, comp_id)] = pt_id

            # Pre-fetch Internal Source Locations
            source_loc_types = list(set(store_pos_delivery_orders.mapped("location_id.cmr_location_type")))
            source_loc_map = {}
            if company_ids and source_loc_types:
                src_res = session.get(
                    f"{base_url}/stock.location/search",
                    params={
                        "domain": str([
                            ("usage", "=", "internal"),
                            ("company_id", "in", company_ids),
                            ("cmr_location_type", "in", source_loc_types),
                        ]),
                        "fields": "['id','cmr_location_type','company_id']",
                    },
                    timeout=120,
                ).json()
                for loc in src_res.get("data", []):
                    loc_type = extract_val(loc.get("cmr_location_type"))
                    comp_id = extract_id(loc.get("company_id"))
                    loc_id = extract_id(loc.get("id"))
                    if loc_type and comp_id and loc_id:
                        source_loc_map[(loc_type, comp_id)] = loc_id

            # Pre-fetch Customer Destination Locations
            dest_names = list(set(store_pos_delivery_orders.mapped("location_dest_id.complete_name")))
            dest_loc_map = {}
            if dest_names:
                dest_res = session.get(
                    f"{base_url}/stock.location/search",
                    params={
                        "domain": str([
                            ("usage", "=", "customer"),
                            ("complete_name", "in", dest_names),
                        ]),
                        "fields": "['id','complete_name']",
                    },
                    timeout=120,
                ).json()
                for d in dest_res.get("data", []):
                    d_name = extract_val(d.get("complete_name"))
                    d_id = extract_id(d.get("id"))
                    if d_name and d_id:
                        dest_loc_map[d_name] = d_id

            # Pre-fetch Products
            all_product_nhcl_ids = list(set(
                store_pos_delivery_orders.move_line_ids_without_package.mapped("product_id.nhcl_id")
            ))
            product_map = {}
            if all_product_nhcl_ids:
                prod_res = session.get(
                    f"{base_url}/product.product/search",
                    params={
                        "domain": str([("nhcl_id", "in", all_product_nhcl_ids)]),
                        "fields": "['id','nhcl_id']",
                    },
                    timeout=120,
                ).json()
                for p in prod_res.get("data", []):
                    p_nhcl = extract_val(p.get("nhcl_id"))
                    p_id = extract_id(p.get("id"))
                    if p_nhcl is not None and p_id:
                        product_map[str(p_nhcl)] = p_id

            # Pre-fetch Employees / Cashiers USING BARCODE
            line_employees = pos_orders.lines.mapped("employ_id.barcode")
            header_employees = pos_orders.mapped("employee_id.barcode")
            all_employee_barcodes = list(filter(None, set(line_employees + header_employees)))
            cashier_map = {}
            if all_employee_barcodes and company_ids:
                cashier_res = session.get(
                    f"{base_url}/hr.employee/search",
                    params={
                        "domain": str([
                            ("barcode", "in", all_employee_barcodes),
                            ("company_id", "in", company_ids),
                        ]),
                        "fields": "['id','barcode','company_id']",
                    },
                    timeout=120,
                ).json()
                for emp in cashier_res.get("data", []):
                    emp_barcode = extract_val(emp.get("barcode"))
                    comp_id = extract_id(emp.get("company_id"))
                    emp_id = extract_id(emp.get("id"))
                    if emp_barcode is not None and comp_id and emp_id:
                        cashier_map[(str(emp_barcode), comp_id)] = emp_id

            # Pre-fetch Taxes
            all_tax_names = list(filter(None, set([
                f"{t.name}-CREDIT"
                for line in pos_orders.lines
                for t in line.tax_ids if t.name
            ])))
            tax_map = {}
            all_target_comp_ids = list(set(company_ids + ([main_company_id] if main_company_id else [])))
            if all_tax_names and all_target_comp_ids:
                tax_res = session.get(
                    f"{base_url}/account.tax/search",
                    params={
                        "domain": str([
                            ("name", "in", all_tax_names),
                            ("company_id", "in", all_target_comp_ids),
                            ("nhcl_creadit_note_tax", "=", True),
                        ]),
                        "fields": "['id','name','company_id']",
                    },
                    timeout=120,
                ).json()
                for t in tax_res.get("data", []):
                    t_name = extract_val(t.get("name"))
                    comp_id = extract_id(t.get("company_id"))
                    t_id = extract_id(t.get("id"))
                    if t_name and comp_id and t_id:
                        tax_map[(t_name, comp_id)] = t_id

            # Pre-fetch Payment Methods
            all_payment_method_names = list(filter(None, set(pos_orders.payment_ids.mapped("payment_method_id.name"))))
            payment_method_map = {}
            if all_payment_method_names:
                pm_res = session.get(
                    f"{base_url}/pos.payment.method/search",
                    params={
                        "domain": str([("name", "in", all_payment_method_names)]),
                        "fields": "['id','name']",
                    },
                    timeout=120,
                ).json()
                for pm in pm_res.get("data", []):
                    pm_name = extract_val(pm.get("name"))
                    pm_id = extract_id(pm.get("id"))
                    if pm_name and pm_id:
                        payment_method_map[pm_name] = pm_id

        except Exception as prefetch_err:
            for order in store_pos_delivery_orders:
                log_order_failure(order, f"Pos Delivery Order Pre-fetch Failure : {order.name} ({str(prefetch_err)})",
                                  mark_failed=False)
            session.close()
            return True

        # =========================================================================
        # 2. IN-MEMORY PAYLOAD BUILDING & INDIVIDUAL POSTING
        # =========================================================================

        already_done_orders = self.env['stock.picking']

        for order in store_pos_delivery_orders:
            try:
                if order.name in existing_origins:
                    already_done_orders |= order
                    continue

                pending_pos_orders = pos_order_map.get(order.origin)
                pos_id = pending_pos_orders.id if pending_pos_orders else False

                ho_partner_id = False
                if pending_pos_orders and pending_pos_orders.partner_id:
                    p = pending_pos_orders.partner_id
                    ho_partner_id = (
                            partner_map.get((p.name, p.phone or False))
                            or partner_map.get(p.name, False)
                            or (p.phone and partner_map.get(p.phone, False))
                    )
                    if not ho_partner_id:
                        log_order_failure(order,
                                          f"Pos Delivery Order Partner Not Found in HO : {order.name} ({p.name})",
                                          mark_failed=True)
                        continue

                company_id = company_map.get(order.company_id.name)
                if not company_id:
                    log_order_failure(order, f"Pos Delivery Order Company Not Found : {order.name}", mark_failed=True)
                    continue

                # Header Employee lookup by BARCODE
                ho_cashier_id = False
                if pending_pos_orders and pending_pos_orders.employee_id and pending_pos_orders.employee_id.barcode:
                    ho_cashier_id = cashier_map.get((str(pending_pos_orders.employee_id.barcode), company_id), False)

                picking_type_ho_id = picking_type_map.get((order.picking_type_id.stock_picking_type, company_id))
                if not picking_type_ho_id:
                    log_order_failure(order, f"Pos Delivery Order Picking Type Not Found : {order.name}",
                                      mark_failed=True)
                    continue

                location_id = source_loc_map.get((order.location_id.cmr_location_type, company_id))
                dest_id = dest_loc_map.get(order.location_dest_id.complete_name)

                if not location_id or not dest_id:
                    log_order_failure(order, f"Pos Delivery Order Location Not Found : {order.name}", mark_failed=True)
                    continue

                picking_payment_lines = []
                has_missing_payment = False

                if pending_pos_orders and pending_pos_orders.payment_ids:
                    for pay in pending_pos_orders.payment_ids:
                        if not pay.payment_method_id:
                            continue
                        ho_pm_id = payment_method_map.get(pay.payment_method_id.name)
                        if not ho_pm_id:
                            log_order_failure(order, f"Pos Delivery Order Payment Method Not Found : {order.name}",
                                              mark_failed=True)
                            has_missing_payment = True
                            break

                        pos_ref = (
                            pay.pos_reference
                            if hasattr(pay, "pos_reference") and pay.pos_reference
                            else (pending_pos_orders.pos_reference or False)
                        )

                        picking_payment_lines.append((0, 0, {
                            "payment_method_id": ho_pm_id,
                            "pos_reference": pos_ref,
                            "amount": pay.amount,
                        }))

                if has_missing_payment:
                    continue

                move_lines = []
                has_missing_line_dependency = False
                company_state_name = order.company_id.state_id.name if order.company_id and order.company_id.state_id else ""

                for line in order.move_line_ids_without_package:
                    product_id = product_map.get(str(line.product_id.nhcl_id))
                    if not product_id:
                        log_order_failure(order, f"Pos Delivery Order Product Not Found : {order.name}",
                                          mark_failed=True)
                        has_missing_line_dependency = True
                        break

                    ho_employee_id = False
                    ho_tax_ids = []
                    pos_line = None

                    if pos_id:
                        if line.lot_id and line.lot_id.name:
                            pos_line = pos_line_by_lot.get((pos_id, line.product_id.id, line.lot_id.name))
                        if not pos_line:
                            pos_line = pos_line_by_prod.get((pos_id, line.product_id.id))

                        if pos_line:
                            emp = pos_line.employ_id or pos_line.employee_id
                            # Line Employee lookup by BARCODE
                            if emp and emp.barcode:
                                ho_employee_id = cashier_map.get((str(emp.barcode), company_id), False)
                                if not ho_employee_id:
                                    log_order_failure(order,
                                                      f"Pos Delivery Order Employee Not Found {emp.name}: {order.name}",
                                                      mark_failed=True)
                                    has_missing_line_dependency = True
                                    break

                            target_tax_comp_id = company_id if company_state_name != "Andhra Pradesh" else main_company_id

                            for t in pos_line.tax_ids:
                                if not t.name:
                                    continue
                                matched_tax_id = tax_map.get((f"{t.name}-CREDIT", target_tax_comp_id))
                                if not matched_tax_id:
                                    log_order_failure(order, f"Pos Delivery Order Tax Not Found {t.name}: {order.name}",
                                                      mark_failed=True)
                                    has_missing_line_dependency = True
                                    break
                                ho_tax_ids.append(matched_tax_id)

                            if has_missing_line_dependency:
                                break

                    move_line_vals = {
                        "product_id": product_id,
                        "quantity": line.quantity,
                        "internal_ref_lot": line.internal_ref_lot or False,
                        "location_id": location_id,
                        "location_dest_id": dest_id,
                        "lot_name": line.lot_id.name if line.lot_id else False,
                        "employ_id": ho_employee_id or False,
                        "tax_ids_after_fiscal_position": [(6, 0, ho_tax_ids)] if ho_tax_ids else [],
                        "total_discount": pos_line.total_discount if pos_line else 0.0,
                        "discount_percentage": pos_line.discount_percentage if pos_line else 0.0,
                        "total_reward_discount": pos_line.total_reward_discount if pos_line else 0.0,
                        "gdiscount": pos_line.gdiscount if pos_line else 0.0,
                        "price_subtotal": pos_line.price_subtotal if pos_line else 0.0,
                        "price_subtotal_incl": pos_line.price_subtotal_incl if pos_line else 0.0,
                        "cost_price": pos_line.nhcl_cost_price if pos_line else 0.0,
                        "rs_price": pos_line.nhcl_rs_price if pos_line else 0.0,
                        "mr_price": pos_line.nhcl_mr_price if pos_line else 0.0,
                        "applied_program": pos_line.applied_program_id.name if pos_line and pos_line.applied_program_id else False,
                        "customer_note": pos_line.customer_note if pos_line and pos_line.customer_note else False,
                        "product_name": pos_line.full_product_name if pos_line and pos_line.full_product_name else False,
                        "cgst_amount": (((
                                                 pos_line.price_subtotal_incl - pos_line.price_subtotal) / 2) if pos_line and pos_line.price_subtotal_incl and pos_line.price_subtotal else 0.0),
                        "sgst_amount": (((
                                                 pos_line.price_subtotal_incl - pos_line.price_subtotal) / 2) if pos_line and pos_line.price_subtotal_incl and pos_line.price_subtotal else 0.0),
                        "badge_id": pos_line.badge_id if pos_line and pos_line.badge_id else False,
                        "fix_discount_amount": pos_line.fix_discount_amount if pos_line else 0.0,
                        "fix_discount_percentage": pos_line.fix_discount_percentage if pos_line else 0.0,
                    }
                    move_lines.append((0, 0, move_line_vals))

                if has_missing_line_dependency or not move_lines:
                    if not move_lines and not has_missing_line_dependency:
                        log_order_failure(order, f"Pos Delivery Order Move Lines Empty : {order.name}",
                                          mark_failed=True)
                    continue

                single_payload = {
                    "picking_type_id": picking_type_ho_id,
                    "partner_id": ho_partner_id,
                    "cashier_id": ho_cashier_id,
                    "origin": order.name,
                    "pos_reference": pending_pos_orders.pos_reference if pending_pos_orders else False,
                    "pos_name": pending_pos_orders.name if pending_pos_orders else False,
                    "date_order": pending_pos_orders.date_order.strftime(
                        "%Y-%m-%d %H:%M:%S") if pending_pos_orders and pending_pos_orders.date_order else False,
                    "date_done": order.date_done.strftime("%Y-%m-%d %H:%M:%S") if order.date_done else False,
                    "scheduled_date": order.scheduled_date.strftime(
                        "%Y-%m-%d %H:%M:%S") if order.scheduled_date else False,
                    "location_id": location_id,
                    "location_dest_id": dest_id,
                    "company_id": company_id,
                    "move_type": "direct",
                    "nhcl_store_delivery": True,
                    "move_line_ids_without_package": move_lines,
                    "picking_payment_ids": picking_payment_lines,
                }

                # =========================================================================
                # 3. DIRECT POST PER PICKING (HANDLES BOTH DICT AND LIST CONTROLLERS)
                # =========================================================================
                res_raw = session.post(
                    f"{base_url}/stock.picking/create",
                    json=single_payload,  # Sends direct dictionary payload
                    timeout=300,
                )

                try:
                    response = res_raw.json()
                except Exception:
                    response = {"raw_error": res_raw.text[:300]}

                is_success = (
                        response.get("success") is True
                        or str(response.get("status")).lower() in ["200", "success", "ok", "true"]
                        or response.get("code") in [200, "200"]
                        or bool(response.get("create_id"))
                        or bool(response.get("ids"))
                )

                if is_success:
                    order.write({"nhcl_replication_status": True})
                else:
                    err_detail = (
                            response.get("message")
                            or response.get("error")
                            or response.get("raw_error")
                            or response.get("reason")
                            or res_raw.text[:300]
                    )
                    log_order_failure(order, f"HO Single Post Failed : {order.name} ({err_detail})", mark_failed=False)

            except Exception as order_err:
                log_order_failure(order, f"Pos Delivery Order Execution Error : {order.name} ({str(order_err)})",
                                  mark_failed=False)

        if already_done_orders:
            already_done_orders.write({"nhcl_replication_status": True})

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
        self.store_pos_delivery_orders()
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
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add',
                                                                     "failure", msg)
                        pos_order.write({
                            'nhcl_integration_count': 'yes',
                        })
                        self.env.cr.commit()
                        break
                    # -------------------- Company --------------------
                    company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                    company_domain = [('name', '=', pos_order.company_id.name)]
                    company_url = f"{company_search}?domain={company_domain}&fields=['id','name']"
                    company_data = requests.get(company_url, headers=headers_source).json()
                    company_id = company_data.get("data")

                    if not company_id:
                        msg = f"Company not found for Pos Order {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        break
                    # -------------------- Session --------------------
                    session_search = f"http://{ho_ip}:{ho_port}/api/pos.session/search"
                    session_domain = [('company_id', '=', company_id[0]['id'])]
                    session_url = f"{session_search}?domain={session_domain}&fields=['id','name']"
                    session_data = requests.get(session_url, headers=headers_source).json()
                    session_id = session_data.get("data")

                    if not session_id:
                        msg = f"Company not found for Session {pos_order.name}"
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        self.env.cr.commit()
                        break

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
                        ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                     'add', "failure", msg)
                        self.env.cr.commit()
                        break

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
                    branch_pos_order_domain = [('name', '=', pos_order.name),
                                               ('pos_reference', '=', pos_order.pos_reference),
                                               ('company_id', '=', company_id[0]['id'])]
                    branch_pos_order_url = f"{branch_pos_order_search}?domain={branch_pos_order_domain}&fields=['id','name','pos_reference']"
                    branch_pos_order_data = requests.get(branch_pos_order_url, headers=headers_source).json()
                    branch_pos_order = branch_pos_order_data.get("data")
                    if branch_pos_order:
                        pos_order.write({
                            'nhcl_status': True
                        })
                        self.env.cr.commit()
                    skip_creation = False
                    pos_line = []

                    for line in pos_order.lines:

                        # ---------------- Product ----------------
                        ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"

                        if line.product_id.detailed_type == 'service':
                            ho_product_domain = [('name', 'ilike', line.product_id.name)]
                        else:
                            ho_product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]

                        product_url = f"{ho_product_url}?domain={ho_product_domain}&fields=['id','name']"
                        ho_product_data = requests.get(product_url, headers=headers_source).json()

                        product_data = ho_product_data.get("data")
                        product_id = product_data[0]["id"] if product_data else False

                        if not product_id:
                            msg = f"Product not found for {line.product_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'POS Order', pos_order.id, pos_order.name,
                                200, 'add', "failure", msg
                            )
                            self.env.cr.commit()
                            skip_creation = True
                            break

                        # ---------------- Service Product ----------------

                        if line.product_id.detailed_type == 'service':
                            pos_line.append((0, 0, {
                                "full_product_name": line.full_product_name,
                                "product_id": product_id,
                                "qty": line.qty,
                                "price_unit": line.price_unit,
                                "price_subtotal": line.price_subtotal,
                                "price_subtotal_incl": line.price_subtotal_incl,
                            }))
                            continue

                        # ---------------- Employee ----------------

                        ho_employee_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                        ho_employee_domain = [
                            ('nhcl_id', '=', line.employ_id.nhcl_id),
                            ('company_id', '=', company_id[0]['id'])
                        ]

                        employee_url = f"{ho_employee_url}?domain={ho_employee_domain}&fields=['id','name']"
                        ho_employee_data = requests.get(employee_url, headers=headers_source).json()

                        employee_data = ho_employee_data.get("data")
                        employee_id = employee_data[0]["id"] if employee_data else False

                        if not employee_id:
                            msg = f"Employee not found for {line.employ_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log(
                                'POS Order', pos_order.id, pos_order.name,
                                200, 'add', "failure", msg
                            )
                            self.env.cr.commit()
                            skip_creation = True
                            break

                        # ---------------- Taxes ----------------

                        tax_ids = []

                        for tax in line.tax_ids:

                            if tax.company_id.state_id.name != 'Andhra Pradesh':
                                tax_domain = [
                                    ('name', '=', f"{tax.name}-CREDIT"),
                                    ('company_id', '=', company_id[0]['id']),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]
                            else:
                                tax_domain = [
                                    ('name', '=', f"{tax.name}-CREDIT"),
                                    ('company_id', '=', main_company_id[0]['id']),
                                    ('nhcl_creadit_note_tax', '=', True)
                                ]

                            tax_url = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                            tax_id_url = f"{tax_url}?domain={tax_domain}&fields=['id','name']"

                            tax_response = requests.get(
                                tax_id_url,
                                headers=headers_source
                            ).json()

                            tax_data = tax_response.get("data")

                            if not tax_data:
                                msg = f"Tax not found for {tax.name}-CREDIT In {pos_order.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'POS Order', pos_order.id, pos_order.name,
                                    200, 'add', "failure", msg
                                )
                                self.env.cr.commit()
                                skip_creation = True
                                break

                            tax_ids.append(tax_data[0]["id"])

                        if skip_creation:
                            break

                        # ---------------- Lots ----------------

                        lot_ids = []

                        for lot in line.pack_lot_ids:

                            pack_operation = self.env['pos.pack.operation.lot'].browse(lot.id)

                            lot_domain = [
                                ('name', '=', pack_operation.lot_name),
                                ('company_id', '=', company_id[0]['id'])
                            ]

                            lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                            lot_id_url = f"{lot_url}?domain={lot_domain}&fields=['id','name']"

                            lot_response = requests.get(
                                lot_id_url,
                                headers=headers_source
                            ).json()

                            lot_data = lot_response.get("data")

                            if not lot_data:
                                msg = f"Lot not found for {pack_operation.lot_name} In {pos_order.name}"
                                ho_id.create_cmr_transaction_replication_log(
                                    'POS Order', pos_order.id, pos_order.name,
                                    200, 'add', "failure", msg
                                )
                                self.env.cr.commit()
                                skip_creation = True
                                break

                            lot_ids.append(lot_data[0]["id"])

                        if skip_creation:
                            break

                        # ---------------- POS Line ----------------

                        pos_order_line = {
                            "full_product_name": line.full_product_name,
                            "product_id": product_id,
                            "qty": line.qty,
                            "price_unit": line.price_unit,
                            "price_subtotal": line.price_subtotal,
                            "price_subtotal_incl": line.price_subtotal_incl,
                            "tax_ids": tax_ids if tax_ids else False,
                            "lot_ids": lot_ids if lot_ids else False,
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

                    # Skip creating POS Order
                    if skip_creation:
                        continue

                    payment_data = []
                    for payment in pos_order.payment_ids:
                        ho_payment_method_url = f"http://{ho_ip}:{ho_port}/api/pos.payment.method/search"
                        ho_payment_method_domain = [('name', '=', payment.payment_method_id.name),
                                                    ('company_id', '=', company_id[0]['id'])]
                        payment_method_url = f"{ho_payment_method_url}?domain={ho_payment_method_domain}&fields=['id','name']"
                        ho_payment_method_data = requests.get(payment_method_url, headers=headers_source).json()
                        payment_method_data = ho_payment_method_data.get('data')
                        if not payment_method_data:
                            msg = f"Payment Method not found for {payment.payment_method_id.name} In {pos_order.name}"
                            ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200,
                                                                         'add', "failure", msg)
                            self.env.cr.commit()
                            break

                        pos_payment_vals = {
                            "payment_date": payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                            "payment_method_id": payment_method_data[0]['id'],
                            "amount": payment.amount,

                        }
                        payment_data.append((0, 0, pos_payment_vals))
                    used_credit_data = []
                    if pos_order.credit_ids:
                        for credit in pos_order.credit_ids:
                            pos_used_credit_vals = {
                                "voucher_number": credit.partner_credit_id.voucher_number,
                                "voucher_amount": credit.amount,

                            }
                            used_credit_data.append((0, 0, pos_used_credit_vals))

                    if not branch_pos_order:
                        if pos_line and payment_data:
                            pos_order_vals = {
                                "partner_id": partner_id,
                                "name": pos_order.name,
                                "pos_reference": pos_order.pos_reference,
                                "tracking_number": pos_order.tracking_number,
                                "session_id": session_id[0]['id'],
                                # "session_id" : 8,
                                "amount_tax": pos_order.amount_tax,
                                "amount_total": pos_order.amount_total,
                                "amount_paid": pos_order.amount_paid,
                                "amount_discount": pos_order.amount_discount,
                                "amount_reward_discount": pos_order.amount_reward_discount,
                                "amount_return": pos_order.amount_return,
                                "company_id": company_id[0]['id'],
                                "lines": pos_line,
                                "payment_ids": payment_data,
                                "voucher_line_ids": used_credit_data,
                                "state": "paid",
                                "nhcl_store_je": True,
                                "date_order": pos_order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                                "employee_id": cashier_id,
                            }
                            branch_pos_order_create_url = f"http://{ho_ip}:{ho_port}/api/pos.order/create"
                            try:
                                branch_pos_data = requests.post(branch_pos_order_create_url, headers=headers_source,
                                                                json=[pos_order_vals])
                                branch_pos_data.raise_for_status()
                                pos_responsc = branch_pos_data.json()
                                if pos_responsc and pos_responsc['success']:
                                    pos_order.write({
                                        'nhcl_status': True
                                    })
                                    self.env.cr.commit()

                                else:

                                    ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id,
                                                                                 pos_order.name, 200, 'add', "failure",
                                                                                 str(pos_responsc))
                                    pos_order.write({
                                        'nhcl_integration_count': 'yes',
                                    })
                                    self.env.cr.commit()

                            except requests.exceptions.RequestException as e:
                                ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name,
                                                                             200, 'add', "failure", str(e))
                                pos_order.write({
                                    'nhcl_integration_count': 'yes',
                                })
                                self.env.cr.commit()
                except Exception as e:
                    msg = f"Unexpected error while processing {pos_order.name}: {e}"
                    ho_id.create_cmr_transaction_replication_log('POS Order', pos_order.id, pos_order.name, 200, 'add',
                                                                 "failure", msg)
                    pos_order.write({
                        'nhcl_integration_count': 'yes',
                    })
                    self.env.cr.commit()
                    continue

        return True

    def remove_records_from_log_table(self):

        failure_records = self.env['nhcl.transaction.replication.log'].search([('nhcl_status','=','failure')])
        # failure_records = self.env['nhcl.transaction.replication.log'].search([('nhcl_record_name','=','CMRCOS/0039')])
        for rec in failure_records:
            if rec.nhcl_model == 'POS Order':
                branch_pos_order = self.env['pos.order'].search([('nhcl_status','=',True), ('name', '=', rec.nhcl_record_name)])
                if branch_pos_order:
                    rec.unlink()
            if rec.nhcl_model == 'Journal Entry':
                branch_journal_entry = self.env['account.move'].search([('nhcl_replication_status','=',True), ('name', '=', rec.nhcl_record_name)])
                if branch_journal_entry:
                    rec.unlink()
            if rec.nhcl_model == 'POS Delivery Order':
                branch_pos_delivery = self.env['stock.picking'].search([('nhcl_replication_status','=',True), ('name', '=', rec.nhcl_record_name)])
                if branch_pos_delivery:
                    rec.unlink()

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


