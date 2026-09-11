import re
from collections import defaultdict

from odoo import models, api, fields, _
import requests
import logging

from odoo.exceptions import ValidationError
from odoo.tools import json
import urllib.parse
_logger = logging.getLogger(__name__)
from datetime import datetime


class StockPicking(models.Model):
    _inherit = "stock.picking"

    warning_message = fields.Char(compute='_compute_warning_message')

    @api.depends('name')
    def _compute_warning_message(self):
        for rec in self:
            rec.warning_message = ''
            if rec.nhcl_replication_status == False:
                rec.warning_message = 'Oops! Integration has not been completed.'
            else:
                rec.warning_message = 'Integration is Complete!'

    def get_main_damage_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "main_damage")],
                                                                        limit=1)
                if not picking_type_id:
                    continue

                store_pos_delivery_orders = self.env['stock.picking'].search([
                    ('picking_type_id', '=', picking_type_id.id),
                    ('nhcl_replication_status', '=', False),
                    ('stock_picking_type', '=', 'main_damage'),
                    ('state', '=', 'done')
                ])

                if not store_pos_delivery_orders:
                    continue

                for order in store_pos_delivery_orders:
                    try:
                        # 1. Fetch Company ID
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', order.company_id.name)]
                        company_url = f"{company_search}?domain={company_domain}&fields=['name','id']"

                        company_res = requests.get(company_url, headers=headers_source).json()
                        company_list = company_res.get("data")

                        if not company_list:
                            error_msg = f"Company '{order.company_id.name}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            order.nhcl_replication_status = False
                            break  # Break record creation completely for this order

                        company_id = company_list[0]['id']

                        # 2. Fetch Picking Type ID at HO
                        ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                        picking_type_domain = [('stock_picking_type', '=', "main_damage"),
                                               ('company_id', '=', company_id)]
                        picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}&fields=['name','id']"

                        picking_type_res = requests.get(picking_type_url, headers=headers_source).json()
                        picking_type = picking_type_res.get("data")

                        if not picking_type:
                            error_msg = "Picking type 'main_damage' not found at HO."
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            order.nhcl_replication_status = False
                            break  # Break record creation completely for this order

                        # 3. Fetch Source & Destination Locations
                        ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"

                        loc_domain = [('cmr_location_type', '=', order.location_id.cmr_location_type),
                                      ('company_id', '=', company_id)]
                        loc_res = requests.get(f"{ho_location_url}?domain={loc_domain}&fields=['name','id']",
                                               headers=headers_source).json()
                        location_id = loc_res.get("data")

                        if not location_id:
                            error_msg = f"Source location type '{order.location_id.cmr_location_type}' not found."
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            order.nhcl_replication_status = False
                            break  # Break record creation completely for this order

                        dest_domain = [('cmr_location_type', '=', order.location_dest_id.cmr_location_type),
                                       ('company_id', '=', company_id)]
                        dest_res = requests.get(f"{ho_location_url}?domain={dest_domain}&fields=['name','id']",
                                                headers=headers_source).json()
                        dest_location = dest_res.get("data")

                        if not dest_location:
                            error_msg = f"Destination location type '{order.location_dest_id.cmr_location_type}' not found."
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            order.nhcl_replication_status = False
                            break  # Break record creation completely for this order

                        # 4. Bulk Mapping Preparations
                        nhcl_product_ids = [line.product_id.nhcl_id for line in order.move_line_ids_without_package if
                                            line.product_id.nhcl_id]

                        cat_nhcl_ids = set()
                        desc_nhcl_ids = set()
                        for line in order.move_line_ids_without_package:
                            for c in [line.categ_1, line.categ_2, line.categ_3, line.categ_4, line.categ_5,
                                      line.categ_6, line.categ_7]:
                                if c and c.nhcl_id: cat_nhcl_ids.add(c.nhcl_id)
                            for d in [line.descrip_1, line.descrip_2, line.descrip_3, line.descrip_4, line.descrip_5,
                                      line.descrip_6]:
                                if d and d.nhcl_id: desc_nhcl_ids.add(d.nhcl_id)

                        # Bulk fetch Products
                        product_map = {}
                        if nhcl_product_ids:
                            prod_domain = [('nhcl_id', 'in', list(nhcl_product_ids))]
                            prod_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={prod_domain}&fields=['name','nhcl_id','id']"
                            p_res = requests.get(prod_url, headers=headers_source).json()
                            p_data = p_res.get("data", [])
                            product_map = {p['nhcl_id']: p['id'] for p in p_data}

                        # Bulk fetch Categories
                        cat_map = {}
                        if cat_nhcl_ids:
                            cat_domain = [('nhcl_id', 'in', list(cat_nhcl_ids))]
                            cat_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search?domain={cat_domain}&fields=['nhcl_id','id']"
                            c_res = requests.get(cat_url, headers=headers_source).json()
                            c_data = c_res.get("data", [])
                            cat_map = {c['nhcl_id']: c['id'] for c in c_data}

                        # Bulk fetch Descriptions
                        desc_map = {}
                        if desc_nhcl_ids:
                            desc_domain = [('nhcl_id', 'in', list(desc_nhcl_ids))]
                            desc_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search?domain={desc_domain}&fields=['nhcl_id','id']"
                            d_res = requests.get(desc_url, headers=headers_source).json()
                            d_data = d_res.get("data", [])
                            desc_map = {d['nhcl_id']: d['id'] for d in d_data}

                        # 5. Validate Line Items (Stop record creation & log ONLY if any value is missing)
                        validation_failed = False
                        validation_error_msg = ""

                        for line in order.move_line_ids_without_package:
                            if not line.product_id.nhcl_id or line.product_id.nhcl_id not in product_map:
                                validation_failed = True
                                validation_error_msg = f"Product missing at HO: {line.product_id.name}"
                                break

                            for attr_name, attr_val in [('categ_1', line.categ_1), ('categ_2', line.categ_2),
                                                        ('categ_3', line.categ_3),
                                                        ('categ_4', line.categ_4), ('categ_5', line.categ_5),
                                                        ('categ_6', line.categ_6), ('categ_7', line.categ_7)]:
                                if attr_val and attr_val.nhcl_id and attr_val.nhcl_id not in cat_map:
                                    validation_failed = True
                                    validation_error_msg = f"Category '{attr_name}' value missing at HO for product {line.product_id.name}"
                                    break

                            if validation_failed:
                                break

                            for desc_name, desc_val in [('descrip_1', line.descrip_1), ('descrip_2', line.descrip_2),
                                                        ('descrip_3', line.descrip_3),
                                                        ('descrip_4', line.descrip_4), ('descrip_5', line.descrip_5),
                                                        ('descrip_6', line.descrip_6)]:
                                if desc_val and desc_val.nhcl_id and desc_val.nhcl_id not in desc_map:
                                    validation_failed = True
                                    validation_error_msg = f"Description '{desc_name}' value missing at HO for product {line.product_id.name}"
                                    break

                            if validation_failed:
                                break

                        if validation_failed:
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure',
                                                                      validation_error_msg)
                            order.nhcl_replication_status = False
                            break  # Break record creation completely for this order

                        # 6. Create Stock Picking Header
                        stock_picking_vals = {
                            'picking_type_id': picking_type[0]['id'],
                            'origin': order.name,
                            'stock_type': order.stock_type,
                            'stock_picking_type': order.stock_picking_type,
                            'location_id': location_id[0]['id'],
                            'location_dest_id': dest_location[0]['id'],
                            'company_id': company_id,
                            'move_type': 'direct',
                            'state': 'done',
                            'nhcl_store_delivery': True
                        }

                        picking_create_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/create"
                        picking_response = requests.post(picking_create_url, headers=headers_source,
                                                         json=[stock_picking_vals])
                        picking_response.raise_for_status()
                        stock_picking_res = picking_response.json()

                        if not stock_picking_res.get("success"):
                            msg = stock_picking_res.get("message", "Unknown error")
                            ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,
                                                                      order.name, 200, 'add', 'failure', msg)
                            order.nhcl_replication_status = False
                            break

                        created_picking_id = stock_picking_res.get("create_id")

                        # 7. Prepare and Create Stock Move Lines
                        move_lines_payload = []
                        for line in order.move_line_ids_without_package:
                            move_line_vals = {
                                "picking_id": created_picking_id,
                                "product_id": product_map.get(line.product_id.nhcl_id),
                                "quantity": line.quantity,
                                "location_id": location_id[0]['id'],
                                "location_dest_id": dest_location[0]['id'],
                                "lot_name": line.lot_id.name if line.lot_id else None,
                                'internal_ref_lot': line.internal_ref_lot,
                                'rs_price': line.rs_price or 0,
                                'cost_price': line.cost_price or 0,
                                'type_product': line.type_product,
                                'segment': line.segment,
                                'categ_1': cat_map.get(line.categ_1.nhcl_id) if line.categ_1 else False,
                                'categ_2': cat_map.get(line.categ_2.nhcl_id) if line.categ_2 else False,
                                'categ_3': cat_map.get(line.categ_3.nhcl_id) if line.categ_3 else False,
                                'categ_4': cat_map.get(line.categ_4.nhcl_id) if line.categ_4 else False,
                                'categ_5': cat_map.get(line.categ_5.nhcl_id) if line.categ_5 else False,
                                'categ_6': cat_map.get(line.categ_6.nhcl_id) if line.categ_6 else False,
                                'categ_7': cat_map.get(line.categ_7.nhcl_id) if line.categ_7 else False,
                                'descrip_1': desc_map.get(line.descrip_1.nhcl_id) if line.descrip_1 else False,
                                'descrip_2': desc_map.get(line.descrip_2.nhcl_id) if line.descrip_2 else False,
                                'descrip_3': desc_map.get(line.descrip_3.nhcl_id) if line.descrip_3 else False,
                                'descrip_4': desc_map.get(line.descrip_4.nhcl_id) if line.descrip_4 else False,
                                'descrip_5': desc_map.get(line.descrip_5.nhcl_id) if line.descrip_5 else False,
                                'descrip_6': desc_map.get(line.descrip_6.nhcl_id) if line.descrip_6 else False,
                            }
                            move_lines_payload.append(move_line_vals)

                        if move_lines_payload:
                            move_line_create_url = f"http://{ho_ip}:{ho_port}/api/stock.move.line/create"
                            ml_response = requests.post(move_line_create_url, headers=headers_source,
                                                        json=move_lines_payload)
                            ml_response.raise_for_status()

                        # Success Handling
                        success_msg = f"Successfully created Delivery Order {order.name}"
                        ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id, order.name,
                                                                  200, 'add', 'success', success_msg)
                        order.nhcl_replication_status = True
                        order.validate_orders(deliver_order='main_damage')
                        break  # Successfully finished this order, break out of loop

                    except Exception as inner_e:
                        ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id, order.name,
                                                                  500, 'add', 'failure', str(inner_e))
                        break

            except Exception as e:
                ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id, order.name,
                                                          500, 'add', 'failure', e)

    def get_damage_main_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage_main")])
                store_pos_delivery_orders = self.env['stock.picking'].search([
                    ('picking_type_id', '=', picking_type_id.id),
                    ('nhcl_replication_status', '=', False),
                    ('stock_picking_type', '=', 'damage_main'),
                    ('state', '=', 'done')
                ])

                if store_pos_delivery_orders:
                    for order in store_pos_delivery_orders:
                        if order.stock_picking_type != "damage_main":
                            continue

                        # --- 1. COMPANY SEARCH ---
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', order.company_id.name)]
                        company_data = requests.get(f"{company_search}?domain={company_domain}",
                                                    headers=headers_source).json()
                        company_id = company_data.get("data")

                        if not company_id:
                            error_msg = f"Company '{order.company_id.name}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break  # Stop processing this order

                        # --- 2. PICKING TYPE SEARCH ---
                        ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                        picking_type_domain = [('stock_picking_type', '=', "damage_main"),
                                               ('company_id', '=', company_id[0]['id'])]
                        picking_type_data = requests.get(f"{ho_stock_picking_type_url}?domain={picking_type_domain}",
                                                         headers=headers_source).json()
                        picking_type = picking_type_data.get("data")

                        if not picking_type:
                            error_msg = f"Picking Type 'damage_main' for company not found at HO."
                            ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # --- 3. LOCATION SEARCHES ---
                        ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"

                        # Source Location Validation
                        location_domain = [('cmr_location_type', '=', order.location_id.cmr_location_type),
                                           ("active", "!=", False), ('usage', '=', 'internal'),
                                           ('company_id', '=', company_id[0]['id'])]
                        location_data = requests.get(f"{ho_location_url}?domain={location_domain}&fields=['name','id']",
                                                     headers=headers_source).json()
                        location_id = location_data.get("data")

                        if not location_id:
                            error_msg = f"Source Location Type '{order.location_id.cmr_location_type}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # Destination Location Validation
                        dest_location_domain = [('cmr_location_type', '=', order.location_dest_id.cmr_location_type),
                                                ("active", "!=", False), ('usage', '=', 'internal')]
                        dest_location_data = requests.get(
                            f"{ho_location_url}?domain={dest_location_domain}&fields=['name','id']",
                            headers=headers_source).json()
                        dest_location = dest_location_data.get("data")

                        if not dest_location:
                            error_msg = f"Destination Location Type '{order.location_dest_id.cmr_location_type}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # --- 4. LINE-BY-LINE LOOKUP & BULK PRE-VALIDATION ---
                        skip_order = False
                        move_lines_payload = []
                        attr_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                        aging_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                        product_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"

                        for line in order.move_line_ids_without_package:
                            # Product Validation
                            product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                            product_data = requests.get(f"{product_search_url}?domain={product_domain}",
                                                        headers=headers_source).json()
                            product_id = product_data.get("data")

                            if not product_id:
                                error_msg = f"Product '{line.product_id.name}' (NHCL ID: {line.product_id.nhcl_id}) not found at HO."
                                ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                          order.name, 200, 'add', 'failure', error_msg)
                                skip_order = True
                                break

                            # Helper function to check categories/attributes dynamically
                            def get_remote_id(field_obj, url, field_label):
                                if not field_obj:
                                    return False
                                domain = [('nhcl_id', '=', field_obj.nhcl_id)]
                                res = requests.get(f"{url}?domain={domain}", headers=headers_source).json().get("data")
                                if res:
                                    return res[0]["id"]
                                else:
                                    nonlocal skip_order, order, ho
                                    err = f"{field_label} '{field_obj.name}' not found at HO for order {order.name}."
                                    _logger.error(err)
                                    ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                              order.name, 200, 'add', 'failure', err)
                                    skip_order = True
                                    return False

                            # Validate Categories (1 to 7)
                            cat_1 = get_remote_id(line.categ_1, attr_search_url, "Category 1")
                            if skip_order: break
                            cat_2 = get_remote_id(line.categ_2, attr_search_url, "Category 2")
                            if skip_order: break
                            cat_3 = get_remote_id(line.categ_3, attr_search_url, "Category 3")
                            if skip_order: break
                            cat_4 = get_remote_id(line.categ_4, attr_search_url, "Category 4")
                            if skip_order: break
                            cat_5 = get_remote_id(line.categ_5, attr_search_url, "Category 5")
                            if skip_order: break
                            cat_6 = get_remote_id(line.categ_6, attr_search_url, "Category 6")
                            if skip_order: break
                            cat_7 = get_remote_id(line.categ_7, attr_search_url, "Category 7")
                            if skip_order: break

                            # Validate Descriptions (1 to 6)
                            desc_1 = get_remote_id(line.descrip_1, aging_search_url, "Description 1")
                            if skip_order: break
                            desc_2 = get_remote_id(line.descrip_2, attr_search_url, "Description 2")
                            if skip_order: break
                            desc_3 = get_remote_id(line.descrip_3, attr_search_url, "Description 3")
                            if skip_order: break
                            desc_4 = get_remote_id(line.descrip_4, attr_search_url, "Description 4")
                            if skip_order: break
                            desc_5 = get_remote_id(line.descrip_5, attr_search_url, "Description 5")
                            if skip_order: break
                            desc_6 = get_remote_id(line.descrip_6, attr_search_url, "Description 6")
                            if skip_order: break

                            # Build payload values for line
                            move_lines_payload.append({
                                "product_id": product_id[0]['id'],
                                "quantity": line.quantity,
                                "location_id": location_id[0]['id'],
                                "location_dest_id": dest_location[0]["id"],
                                "lot_name": line.lot_id.name if line.lot_id else None,
                                'internal_ref_lot': line.internal_ref_lot,
                                'rs_price': line.rs_price or 0,
                                'cost_price': line.cost_price or 0,
                                'type_product': line.type_product,
                                'segment': line.segment,
                                'categ_1': cat_1,
                                'categ_2': cat_2,
                                'categ_3': cat_3,
                                'categ_4': cat_4,
                                'categ_5': cat_5,
                                'categ_6': cat_6,
                                'categ_7': cat_7,
                                'descrip_1': desc_1,
                                'descrip_2': desc_2,
                                'descrip_3': desc_3,
                                'descrip_4': desc_4,
                                'descrip_5': desc_5,
                                'descrip_6': desc_6,
                            })

                        if skip_order:
                            break  # Skip header creation if any line lookup failed

                        # --- 5. CREATE STOCK PICKING HEADER ---
                        stock_picking_payload = {
                            'picking_type_id': picking_type[0]['id'],
                            'origin': order.name,
                            'stock_type': order.stock_type,
                            'stock_picking_type': order.stock_picking_type,
                            'location_id': location_id[0]['id'],
                            'location_dest_id': dest_location[0]['id'],
                            'company_id': company_id[0]['id'],
                            'move_type': 'direct',
                            'state': 'done',
                            'nhcl_store_delivery': True
                        }

                        stock_picking_res_raw = requests.post(f"http://{ho_ip}:{ho_port}/api/stock.picking/create",
                                                              headers=headers_source, json=[stock_picking_payload])
                        stock_picking_res_raw.raise_for_status()
                        stock_picking_res = stock_picking_res_raw.json()

                        if not stock_picking_res.get("success"):
                            message = stock_picking_res.get("message", "Unknown error creating picking")
                            ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', message)
                            continue

                        created_picking_id = stock_picking_res.get("create_id")

                        # --- 6. ATTACH MOVE LINES & FINISH ---
                        for move_line in move_lines_payload:
                            move_line["picking_id"] = created_picking_id
                            requests.post(f"http://{ho_ip}:{ho_port}/api/stock.move.line/create",
                                          headers=headers_source, json=[move_line])

                        # Success Logging & State Update
                        success_msg = f"Successfully created Delivery Order {order.name}"
                        ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id, order.name,
                                                                  200, 'add', 'success', success_msg)
                        order.nhcl_replication_status = True
                        order.validate_orders(deliver_order='damage_main')

            except Exception as e:
                ho.create_cmr_transaction_replication_log("Damage to Main Delivery Order", order.id, order.name, 500,
                                                          'add',
                                                          'failure', str(e))

    def validate_orders(env_or_self, deliver_order, session=None, origins=None):
        """
        Triggers validation on HO server over HTTP.
        Can be called directly as an environment function or as a recordset method.
        """
        env = env_or_self.env if hasattr(env_or_self, 'env') else env_or_self

        ho_id = env["nhcl.ho.store.master"].search(
            [("nhcl_store_type", "=", "ho"), ("nhcl_active", "=", True)], limit=1
        )

        if not ho_id:
            return False

        ho_ip = ho_id.nhcl_terminal_ip
        ho_port = ho_id.nhcl_port_no
        store_api_key = ho_id.nhcl_api_key
        headers = {
            "api-key": f"{store_api_key}",
            "Content-Type": "application/json",
        }

        if deliver_order == "pos_order":
            ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/call_action"
        elif deliver_order == "damage_main":
            ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/damage_main_action"
        elif deliver_order == "main_damage":
            ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/main_damage_action"
        else:
            ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/call_action"

        payload = {}
        if origins:
            payload["origins"] = origins if isinstance(origins, list) else [origins]

        try:
            http_client = session if session else requests
            response = http_client.post(
                ho_pick_validate_url,
                headers=headers,
                json=payload,
                timeout=120,
            )
            res_data = response.json()
            result = res_data.get("result", res_data)
            return result.get("status") in ["success", "partial_success"]

        except Exception as e:
            _logger.error("Failed to execute HO validation HTTP request: %s", str(e))
            return False

    def confirm_orders(self):
        ho_id = self.env["nhcl.ho.store.master"].search(
            [("nhcl_store_type", "=", "ho"), ("nhcl_active", "=", True)], limit=1
        )

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key

                headers_source = {
                    'api-key': f"{store_api_key}",
                    'Content-Type': 'application/json'
                }
                ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/sale.order/call_action"

                # Make the POST request
                ho_pick_data = requests.post(ho_pick_validate_url, json={}, headers=headers_source, timeout=1200)
                ho_pick_data.raise_for_status()

                # Parse JSON response from the server
                response_json = ho_pick_data.json()
                print("API Response:", response_json)

                # Handle Odoo JSON-RPC standard format response wrapper if present
                result = response_json.get('result', response_json)
                ho.create_cmr_transaction_replication_log(
                    'Sale Order',
                    0,  # Record ID (0 or False since it's a general connection failure)
                    'API Request',  # Reference name
                    200,  # Status / Error code
                    'add',  # Action type
                    'success',  # State
                    response_json  # Error description
                )

                # Optional: If the controller returns a list of failed orders,
                # you can also loop and log individual server-side failures here if needed.
                failed_list = result.get('failed', [])
                for fail in failed_list:
                    print(f"Order {fail.get('order_name')} failed: {fail.get('error_reason')}")
                    # If you want to log server-side failures on the client side as well:
                    # ho.create_cmr_transaction_replication_log('Sale Order', 0, fail.get('order_name'), 500, 'add', 'failure', fail.get('error_reason'))

            except Exception as e:
                error_msg = str(e)

                # Log connection or HTTP-level errors using your custom log method
                # Adjust parameters according to how your log method expects them:
                # e.g., (model_name, record_id, record_name, status_code, action_type, state, error_message)
                ho.create_cmr_transaction_replication_log(
                    'Sale Order',
                    0,  # Record ID (0 or False since it's a general connection failure)
                    'API Request',  # Reference name
                    500,  # Status / Error code
                    'add',  # Action type
                    'failure',  # State
                    error_msg  # Error description
                )


    def get_return_main_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            order = None
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # --- Helper function for safe API requests & JSON parsing ---
                def _make_api_request(method, url, **kwargs):
                    try:
                        if method.lower() == 'get':
                            response = requests.get(url, headers=headers_source, **kwargs)
                        elif method.lower() == 'post':
                            response = requests.post(url, headers=headers_source, **kwargs)
                        else:
                            raise ValueError(f"Unsupported HTTP method: {method}")

                        if response.status_code != 200:
                            error_snippet = response.text[:300].replace('\n', ' ')
                            raise Exception(f"HTTP {response.status_code} Error. Response preview: {error_snippet}")

                        return response.json()
                    except json.JSONDecodeError as jde:
                        raise Exception(
                            f"API returned invalid JSON (HTML/Text crash). Check server logs for URL: {url}")
                    except Exception as e:
                        raise e

                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "return_main")])

                for order in self:
                        if order.stock_picking_type != "return_main":
                            continue

                        # --- 1. COMPANY SEARCH ---
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = f"[('name','=','{order.company_id.name}')]"
                        company_data = _make_api_request('get',
                                                         f"{company_search}?domain={urllib.parse.quote(company_domain)}")
                        company_id = company_data.get("data")

                        if not company_id:
                            error_msg = f"Company '{order.company_id.name}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # --- 2. PICKING TYPE SEARCH ---
                        ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                        picking_type_domain = f"[('stock_picking_type','=','return_main'),('company_id','=',{company_id[0]['id']})]"
                        picking_type_data = _make_api_request('get',
                                                              f"{ho_stock_picking_type_url}?domain={urllib.parse.quote(picking_type_domain)}")
                        picking_type = picking_type_data.get("data")

                        if not picking_type:
                            error_msg = f"Picking Type 'return_main' for company not found at HO."
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # --- 3. LOCATION SEARCHES ---
                        ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"

                        # Source Location
                        location_domain = f"[('complete_name','=','{order.location_id.complete_name}'),('active','!=',False),('usage','=','internal'),('company_id','=',{company_id[0]['id']})]"
                        location_data = _make_api_request('get',
                                                          f"{ho_location_url}?domain={urllib.parse.quote(location_domain)}&fields=['name','id']")
                        location_id = location_data.get("data")

                        if not location_id:
                            error_msg = f"Source Location '{order.location_id.complete_name}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # Destination Location
                        dest_location_domain = f"[('complete_name','=','{order.location_dest_id.complete_name}'),('active','!=',False),('usage','=','internal')]"
                        dest_location_data = _make_api_request(
                            'get',
                            f"{ho_location_url}?domain={urllib.parse.quote(dest_location_domain)}&fields=['name','id']"
                        )
                        dest_location = dest_location_data.get("data")

                        if not dest_location:
                            error_msg = f"Destination Location '{order.location_dest_id.complete_name}' not found at HO."
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            break

                        # --- 4. LINE-BY-LINE SEARCH & VALIDATION ---
                        skip_order = False
                        move_lines_payload = []

                        for line in order.move_line_ids_without_package:
                            product_id = None

                            # Check specifically if THIS individual product is a service
                            is_service = getattr(line.product_id, "nhcl_detailed_type", "") == "service"

                            if is_service:
                                prod_name_escaped = line.product_id.name.replace("'", "\\'")
                                product_domain = f"[('name','=','{prod_name_escaped}')]"
                            else:
                                product_domain = f"[('nhcl_id','=',{line.product_id.nhcl_id})]"

                            product_data = _make_api_request(
                                'get',
                                f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={urllib.parse.quote(product_domain)}&fields=['id']"
                            )

                            if product_data.get("data"):
                                product_id = product_data["data"][0]['id']

                            # If still not found, log failure and skip order
                            if not product_id:
                                error_msg = f"Product '{line.product_id.name}' (NHCL ID: {line.product_id.nhcl_id}) not found at HO."
                                ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                          order.name, 200, 'add', 'failure', error_msg)
                                skip_order = True
                                break

                            # Build Move Line Values using Odoo command tuple format (0, 0, {...})
                            move_line_vals = (
                                0,
                                0,
                                {
                                    "product_id": product_id,
                                    "quantity": line.quantity,
                                    "location_id": location_id[0]['id'],
                                    "location_dest_id": dest_location[0]["id"],
                                    "lot_name": line.lot_id.name if line.lot_id else None,
                                    'internal_ref_lot': line.internal_ref_lot,
                                    'rs_price': line.rs_price or 0,
                                    'cost_price': line.cost_price or 0,
                                    'type_product': line.type_product,
                                    'segment': line.segment,
                                }
                            )
                            move_lines_payload.append(move_line_vals)

                        if skip_order:
                            break

                        # --- 5. CREATE STOCK PICKING HEADER ---
                        if not move_lines_payload:
                            error_msg = f"No valid move lines found for order {order.name}. Skipping picking creation."
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            continue

                        stock_picking_data = {
                            'picking_type_id': picking_type[0]['id'],
                            'origin': order.name,
                            'date_done': order.date_done.strftime('%Y-%m-%d %H:%M:%S'),
                            'scheduled_date': order.scheduled_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'stock_type': order.stock_type,
                            'stock_picking_type': order.stock_picking_type,
                            'location_id': location_id[0]['id'],
                            'location_dest_id': dest_location[0]['id'],
                            'company_id': company_id[0]['id'],
                            'move_type': 'direct',
                            'state': 'done',
                            'nhcl_store_delivery': True,
                            'move_line_ids_without_package': move_lines_payload,
                        }

                        stock_picking_res = _make_api_request('post',
                                                              f"http://{ho_ip}:{ho_port}/api/stock.picking/create",
                                                              json=[stock_picking_data])

                        if not stock_picking_res.get("success"):
                            error_msg = stock_picking_res.get("message", "Unknown error creating picking")
                            ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,
                                                                      order.name, 200, 'add', 'failure', error_msg)
                            continue

                        created_picking_id = stock_picking_res.get("create_id")

                        # --- 6. ATTACH MOVE LINES & FINISH ---

                        # Success Logging & State Change
                        ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id, order.name,
                                                                  200, 'add', 'success',
                                                                  f"Successfully created Delivery Order {order.name}")
                        order.nhcl_replication_status = True

            except Exception as e:
                order_id = order.id if 'order' in locals() and order and hasattr(order, 'id') else False
                order_name = order.name if 'order' in locals() and order and hasattr(order, 'name') else 'Unknown'

                if isinstance(e, dict):
                    error_msg = str(e.get('message', e))
                elif hasattr(e, 'args') and e.args and isinstance(e.args[0], dict):
                    error_msg = str(e.args[0].get('message', e.args[0]))
                else:
                    error_msg = str(e)

                ho.create_cmr_transaction_replication_log("Return to Main Delivery Order", order_id, order_name, 500,
                                                          'add',
                                                          'failure', error_msg)


    def get_pos_customer_exchange_recipt_orders(self):
        ho_stores = self.env["nhcl.ho.store.master"].search(
            [("nhcl_store_type", "=", "ho"), ("nhcl_active", "=", True)]
        )
        if not ho_stores:
            return

        picking_type = self.env["stock.picking.type"].search(
            [("stock_picking_type", "=", "exchange")], limit=1
        )
        if not picking_type:
            return



        def safe_json_get(url, headers):
            res = requests.get(url, headers=headers, timeout=120)
            res.raise_for_status()
            try:
                return res.json()
            except json.JSONDecodeError as exc:
                raise Exception(
                    f"Invalid JSON returned from API (Response length: {len(res.text)} chars): {str(exc)}"
                ) from exc

        for ho in ho_stores:
            headers_source = {
                "api-key": ho.nhcl_api_key,
                "Content-Type": "application/json",
            }
            base_url = f"http://{ho.nhcl_terminal_ip}:{ho.nhcl_port_no}/api"

            # Pre-fetch Main Company ID from HO
            try:
                main_comp_res = safe_json_get(
                    f"{base_url}/res.company/search?domain=[('nhcl_company_bool','=',True)]&fields=['id']",
                    headers_source,
                )
                main_company_id = (
                    main_comp_res.get("data")[0]["id"]
                    if main_comp_res.get("data")
                    else None
                )
            except Exception:
                main_company_id = None

            # Iterate over all 10 exchange orders
            for order in self:
                try:
                    # -------------------------------------------------------------
                    # 1. Fetch Company & State Name
                    # -------------------------------------------------------------
                    comp_name_escaped = order.company_id.name.replace("'", "\\'")
                    domain_comp = (
                        f"[('name','=','{comp_name_escaped}')]"
                    )
                    res_company = safe_json_get(
                        f"{base_url}/res.company/search?domain={urllib.parse.quote(domain_comp)}&fields=['id','state_id']",
                        headers_source,
                    )

                    if not res_company.get("data"):
                        msg = f"Company '{order.company_id.name}' not found in HO."
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            404,
                            "add",
                            "failure",
                            msg,
                        )
                        continue

                    comp_data = res_company["data"][0]
                    company_id = comp_data["id"]

                    state_val = comp_data.get("state_id")
                    company_state_name = (
                        state_val[1]
                        if isinstance(state_val, list) and len(state_val) > 1
                        else ""
                    )

                    # -------------------------------------------------------------
                    # PRE-CHECK: Prevent Duplicate Pickings in HO
                    # -------------------------------------------------------------
                    check_domain = f"[('origin','=','{order.name}'),('company_id','=',{company_id})]"
                    existing_picking = safe_json_get(
                        f"{base_url}/stock.picking/search?domain={urllib.parse.quote(check_domain)}&fields=['id']",
                        headers_source,
                    )

                    if existing_picking.get("data"):
                        order.nhcl_replication_status = True
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            200,
                            "add",
                            "success",
                            f"Order {order.name} already exists in HO. Flagging as replicated.",
                        )
                        continue

                    # -------------------------------------------------------------
                    # 2. Fetch Source Location
                    # -------------------------------------------------------------
                    loc_name_escaped = (
                        order.location_id.complete_name.replace("'", "\\'")
                    )
                    domain_loc = f"[('complete_name','=','{loc_name_escaped}'),('active','!=',False)]"
                    res_loc = safe_json_get(
                        f"{base_url}/stock.location/search?domain={urllib.parse.quote(domain_loc)}&fields=['id']",
                        headers_source,
                    )
                    if not res_loc.get("data"):
                        msg = f"Source Location '{order.location_id.complete_name}' not found in HO."
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            404,
                            "add",
                            "failure",
                            msg,
                        )
                        continue
                    location_id = res_loc["data"][0]["id"]

                    # -------------------------------------------------------------
                    # 3. Fetch Destination Location
                    # -------------------------------------------------------------
                    domain_dest = f"[('cmr_location_type','=','{order.location_dest_id.cmr_location_type}'),('active','!=',False),('company_id','=',{company_id})]"
                    res_dest = safe_json_get(
                        f"{base_url}/stock.location/search?domain={urllib.parse.quote(domain_dest)}&fields=['id']",
                        headers_source,
                    )
                    if not res_dest.get("data"):
                        msg = f"Destination Location type '{order.location_dest_id.cmr_location_type}' not found in HO."
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            404,
                            "add",
                            "failure",
                            msg,
                        )
                        continue
                    dest_location_id = res_dest["data"][0]["id"]

                    # -------------------------------------------------------------
                    # 4. Fetch / Create Partner
                    # -------------------------------------------------------------
                    partner_id = None
                    phone = order.partner_id.phone or order.partner_id.mobile

                    if phone:
                        domain_partner = f"[('phone','=','{phone}')]"
                        partner_res = safe_json_get(
                            f"{base_url}/res.partner/search?domain={urllib.parse.quote(domain_partner)}&fields=['id']",
                            headers_source,
                        )
                        if partner_res.get("data"):
                            partner_id = partner_res["data"][0]["id"]

                    if not partner_id:
                        domain_cat = "[('name','=','Customer')]"
                        cat_res = safe_json_get(
                            f"{base_url}/res.partner.category/search?domain={urllib.parse.quote(domain_cat)}&fields=['id']",
                            headers_source,
                        )
                        cat_id = (
                            cat_res.get("data")[0]["id"]
                            if cat_res.get("data")
                            else False
                        )

                        p_data = {
                            "name": order.partner_id.name,
                            "phone": phone,
                            "group_contact": cat_id,
                        }
                        create_res = requests.post(
                            f"{base_url}/res.partner/create",
                            headers=headers_source,
                            json=[p_data],
                            timeout=120,
                        )
                        create_res.raise_for_status()
                        partner_id = create_res.json().get("create_id")

                    if not partner_id:
                        msg = f"Partner '{order.partner_id.name}' (Phone: {phone}) could not be found or created in HO."
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            404,
                            "add",
                            "failure",
                            msg,
                        )
                        continue

                    # -------------------------------------------------------------
                    # 5. Fetch Picking Type
                    # -------------------------------------------------------------
                    domain_pk_type = f"[('stock_picking_type','=','{order.picking_type_id.stock_picking_type}'),('company_id','=',{company_id})]"
                    pk_type_res = safe_json_get(
                        f"{base_url}/stock.picking.type/search?domain={urllib.parse.quote(domain_pk_type)}&fields=['id']",
                        headers_source,
                    )
                    if not pk_type_res.get("data"):
                        msg = f"Picking Type '{order.picking_type_id.name}' not found in HO for Company ID {company_id}."
                        ho.create_cmr_transaction_replication_log(
                            "POS Customer Exchange Receipt Order",
                            order.id,
                            order.name,
                            404,
                            "add",
                            "failure",
                            msg,
                        )
                        continue
                    ho_picking_type_id = pk_type_res["data"][0]["id"]

                    # -------------------------------------------------------------
                    # 6. Build Stock Move Lines
                    # -------------------------------------------------------------
                    stock_detail_lines = []
                    line_error_occurred = False

                    for move in order.move_ids_without_package:
                        # Check specifically if THIS individual product is a service
                        is_service = getattr(move.product_id, "nhcl_detailed_type", "") == "service"

                        if is_service:
                            prod_name_escaped = move.product_id.name.replace("'", "\\'")
                            p_domain_str = f"[('name','=','{prod_name_escaped}')]"
                        else:
                            p_domain_str = f"[('nhcl_id','=',{move.product_id.nhcl_id})]"

                        prod_res = safe_json_get(
                            f"{base_url}/product.product/search?domain={urllib.parse.quote(p_domain_str)}&fields=['id']",
                            headers_source,
                        )

                        if not prod_res.get("data"):
                            msg = f"Product '{move.product_id.name}' (nhcl_id: {move.product_id.nhcl_id}) not found in HO."
                            ho.create_cmr_transaction_replication_log(
                                "POS Customer Exchange Receipt Order",
                                order.id,
                                order.name,
                                404,
                                "add",
                                "failure",
                                msg,
                            )
                            line_error_occurred = True
                            break

                        product_id = prod_res["data"][0]["id"]

                        # Taxes lookup based on company state and credit note tax rules
                        ho_tax_ids = []
                        has_missing_tax = False
                        move_taxes = (
                            move.nhcl_tax_ids
                            if hasattr(move, "nhcl_tax_ids") and move.nhcl_tax_ids
                            else move.nhcl_tax_ids
                        )

                        for tax in move_taxes:
                            if not tax.name:
                                continue

                            if (
                                    tax.company_id
                                    and tax.company_id.state_id
                                    and tax.company_id.state_id.name != "Andhra Pradesh"
                            ):
                                target_comp_for_tax = company_id
                            else:
                                target_comp_for_tax = main_company_id or company_id

                            tax_name = f"{tax.name}-CREDIT"
                            tax_domain = f"[('name','=','{tax_name}'),('company_id','=',{target_comp_for_tax}),('nhcl_creadit_note_tax','=',True)]"
                            tax_res = safe_json_get(
                                f"{base_url}/account.tax/search?domain={urllib.parse.quote(tax_domain)}&fields=['id']",
                                headers_source,
                            )

                            if tax_res.get("data"):
                                ho_tax_ids.append(tax_res["data"][0]["id"])
                            else:
                                msg = f"Pos Delivery Order Tax Not Found '{tax_name}' for Company ID {target_comp_for_tax}: {order.name}"
                                ho.create_cmr_transaction_replication_log(
                                    "POS Customer Exchange Receipt Order",
                                    order.id,
                                    order.name,
                                    404,
                                    "add",
                                    "failure",
                                    msg,
                                )
                                has_missing_tax = True
                                break

                        if has_missing_tax:
                            line_error_occurred = True
                            break

                        lot_name = None
                        if hasattr(move, "lot_id") and move.lot_id:
                            lot_name = move.lot_id.name
                        elif (
                                hasattr(move, "move_line_ids")
                                and move.move_line_ids
                                and move.move_line_ids[0].lot_id
                        ):
                            lot_name = move.move_line_ids[0].lot_id.name

                        stock_detail_lines.append(
                            (
                                0,
                                0,
                                {
                                    "product_id": product_id,
                                    "cost_price": getattr(move, "cost_price", 0.0),
                                    "quantity": getattr(
                                        move,
                                        "product_uom_qty",
                                        getattr(move, "quantity", 0.0),
                                    ),
                                    "location_id": location_id,
                                    "location_dest_id": dest_location_id,
                                    "lot_name": lot_name,
                                    "internal_ref_lot": move.move_line_ids[0].lot_id.ref,
                                    "rs_price": getattr(move, "nhcl_rsp", 0.0),
                                    "mr_price": move.move_line_ids[0].lot_id.mr_price,
                                    "price_subtotal": getattr(
                                        move, "nhcl_price_subtotal", 0.0
                                    ),
                                    "price_subtotal_incl": getattr(
                                        move, "nhcl_price_total", 0.0
                                    ),
                                    "type_product": getattr(
                                        move, "type_product", False
                                    ),
                                    "segment": move.move_line_ids[0].lot_id.segment,
                                    "tax_ids_after_fiscal_position": (
                                        [(6, 0, ho_tax_ids)] if ho_tax_ids else []
                                    ),
                                    "discount_percentage": getattr(
                                        move, "nhcl_discount", 0.0
                                    ),
                                    "total_reward_discount": getattr(
                                        move, "total_reward_discount", 0.0
                                    ),
                                    "gdiscount": getattr(
                                        move, "nhcl_gdiscount", 0.0
                                    ),
                                    "cgst_amount": (
                                        (
                                                (
                                                        getattr(move, "nhcl_price_total", 0.0)
                                                        - getattr(
                                                    move, "nhcl_price_subtotal", 0.0
                                                )
                                                )
                                                / 2
                                        )
                                        if move
                                           and getattr(move, "nhcl_price_total", 0.0)
                                           and getattr(
                                            move, "nhcl_price_subtotal", 0.0
                                        )
                                        else 0.0
                                    ),
                                    "sgst_amount": (
                                        (
                                                (
                                                        getattr(move, "nhcl_price_total", 0.0)
                                                        - getattr(
                                                    move, "nhcl_price_subtotal", 0.0
                                                )
                                                )
                                                / 2
                                        )
                                        if move
                                           and getattr(move, "nhcl_price_total", 0.0)
                                           and getattr(
                                            move, "nhcl_price_subtotal", 0.0
                                        )
                                        else 0.0
                                    ),
                                },
                            )
                        )

                    if line_error_occurred:
                        continue

                    # -------------------------------------------------------------
                    # 7. Post Stock Picking to HO
                    # -------------------------------------------------------------
                    if stock_detail_lines:
                        stock_picking_data = {
                            "partner_id": partner_id,
                            "picking_type_id": ho_picking_type_id,
                            "origin": order.name,
                            "return_counter": order.return_counter.name,
                            "date_order": order.date_time_nh.strftime(
                                "%Y-%m-%d %H:%M:%S") if order and order.date_time_nh else False,
                            "pos_reference": order.nhcl_pos_order.pos_reference if order.nhcl_pos_order else order.store_pos_order,
                            "customer_phone": order.customer_phone,
                            "responsible": order.user_id.name,
                            "ref_credit_note": order.ref_credit_note.name,
                            "date_done": order.date_done.strftime("%Y-%m-%d %H:%M:%S") if order.date_done else False,
                            "scheduled_date": order.scheduled_date.strftime(
                                "%Y-%m-%d %H:%M:%S") if order.scheduled_date else False,
                            "location_id": location_id,
                            "location_dest_id": dest_location_id,
                            "company_id": company_id,
                            "stock_type": "pos_exchange",
                            "company_type": order.company_type,
                            "nhcl_store_delivery": True,
                            "move_line_ids_without_package": stock_detail_lines,
                        }

                        resp = requests.post(
                            f"{base_url}/stock.picking/create",
                            headers=headers_source,
                            json=stock_picking_data,
                            timeout=120,
                        )
                        resp.raise_for_status()
                        stock_picking = resp.json()

                        if stock_picking.get("success"):
                            order.nhcl_replication_status = True
                            ho.create_cmr_transaction_replication_log(
                                "POS Customer Exchange Receipt Order",
                                order.id,
                                order.name,
                                200,
                                "add",
                                "success",
                                f"Successfully created: {order.name}",
                            )
                        else:
                            msg = stock_picking.get(
                                "message", "Unknown HO creation error"
                            )
                            if "already exists" in msg.lower():
                                order.nhcl_replication_status = True

                            ho.create_cmr_transaction_replication_log(
                                "POS Customer Exchange Receipt Order",
                                order.id,
                                order.name,
                                400,
                                "add",
                                "failure",
                                msg,
                            )

                except requests.exceptions.Timeout:
                    err_msg = f"Connection timeout reached while communicating with HO for order {order.name}"
                    ho.create_cmr_transaction_replication_log(
                        "POS Customer Exchange Receipt Order",
                        order.id,
                        order.name,
                        504,
                        "add",
                        "failure",
                        err_msg,
                    )
                except Exception as e:
                    ho.create_cmr_transaction_replication_log(
                        "POS Customer Exchange Receipt Order",
                        order.id,
                        order.name,
                        500,
                        "add",
                        "failure",
                        str(e),
                    )

    # def get_pos_customer_exchange_recipt_orders(self):
    #     ho_id = self.env['nhcl.ho.store.master'].search(
    #         [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])
    #
    #     for ho in ho_id:
    #         try:
    #             ho_ip = ho.nhcl_terminal_ip
    #             ho_port = ho.nhcl_port_no
    #             store_api_key = ho.nhcl_api_key
    #             headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
    #
    #             # Fetch the correct picking type for "Product Exchange - POS"
    #             picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "exchange")])
    #             store_pos_delivery_orders = self.env['stock.picking'].search(
    #                 [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
    #                  ('state', '=', 'done')])
    #             if store_pos_delivery_orders:
    #                 try:
    #                     for order in self:
    #                         if order.stock_picking_type == "exchange":
    #                             # Fetch the company from HO
    #                             company_url = f"http://{ho_ip}:{ho_port}/api/res.company/search?domain=[('name','=', '{order.company_id.name}')]"
    #                             company_data = requests.get(company_url, headers=headers_source).json()
    #                             company_id = company_data.get("data", [])
    #
    #                             if not company_id:
    #                                 logging.warning(
    #                                     f"Company {order.company_id.name} not found in HO. Skipping order {order.name}.")
    #                                 continue  # Skip this order and move to the next one
    #
    #                             company_id = company_id[0]['id']
    #                             print("company_idjjhjj", company_id)
    #                             # Fetch the location from HO
    #                             location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('complete_name','=', '{order.location_id.complete_name}'),('active','!=',False)]&fields=['name','id']"
    #                             location_data = requests.get(location_url, headers=headers_source).json()
    #                             location_id = location_data.get("data", [])
    #
    #                             if not location_id:
    #                                 logging.warning(
    #                                     f"Location {order.location_id.name} not found in HO. Skipping order {order.name}.")
    #                                 continue  # Skip this order and move to the next one
    #
    #                             location_id = location_id[0]['id']
    #
    #                             # Fetch the destination location from HO
    #                             dest_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('cmr_location_type','=', '{order.location_dest_id.cmr_location_type}'),('active','!=',False)]&fields=['name','id']"
    #                             dest_location_data = requests.get(dest_location_url, headers=headers_source).json()
    #                             dest_location_id = dest_location_data.get("data", [])
    #
    #                             if not dest_location_id:
    #                                 logging.warning(
    #                                     f"Destination Location {order.location_dest_id.complete_name} not found in HO. Skipping order {order.name}.")
    #                                 continue  # Skip this order and move to the next one
    #
    #                             dest_location_id = dest_location_id[0]['id']
    #
    #                             # Fetch or create the partner in HO
    #                             partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{order.partner_id.name}'),('phone','=', '{order.partner_id.phone}')]"
    #                             partner_data = requests.get(partner_url, headers=headers_source).json()
    #                             partner = partner_data.get("data", [])
    #                             new_partner = False
    #                             if not partner:
    #                                 line_partner_category_data = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
    #                                 line_partner_category_data_domain = [('name', '=', 'Customer')]
    #                                 line_partner_category_data_url = f"{line_partner_category_data}?domain={line_partner_category_data_domain}"
    #                                 pos_partner_category = requests.get(line_partner_category_data_url,
    #                                                                     headers=headers_source).json()
    #                                 pos_partner_category_id = None
    #                                 if pos_partner_category and pos_partner_category.get("data"):
    #                                     pos_partner_category_id = pos_partner_category.get("data")[0]['id']
    #                                 partner_data = {
    #                                     'name': order.partner_id.name,
    #                                     'phone': order.partner_id.phone,
    #                                     'group_contact': pos_partner_category_id
    #                                 }
    #                                 partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
    #                                 partner_create_response = requests.post(partner_create_url, headers=headers_source,
    #                                                                         json=[partner_data])
    #                                 partner_create_response.raise_for_status()
    #                                 new_partner = partner_create_response.json().get("create_id")
    #
    #                             partner_id = partner[0]['id'] if partner else new_partner
    #
    #                             # Fetch or create the Picking Type ID in HO
    #                             picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search?domain=[('name','=', '{order.picking_type_id.name}'),('company_id','=', {company_id})]"
    #                             picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
    #                             picking_type = picking_type_data.get("data", [])
    #                             # Determine the stock picking data based on 'same store' or 'other store'
    #                             # Create stock move lines
    #                             stock_detail_lines = []
    #                             service = order.move_line_ids_without_package.filtered_domain(
    #                                 [('product_id.nhcl_detailed_type', '=', 'service')])
    #                             for line in order.move_line_ids_without_package:
    #                                 if service:
    #                                     product_domain = [('name', '=', line.product_id.name)]
    #                                 else:
    #                                     product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
    #                                 product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"
    #                                 product_data = requests.get(product_url, headers=headers_source).json()
    #                                 product_id = product_data.get("data", [])
    #
    #                                 if not product_id:
    #                                     logging.warning(
    #                                         f"Product {line.product_id.name} not found in HO. Skipping move line for order {order.name}.")
    #                                     continue  # Skip this move line and move to the next
    #
    #                                 product_id = product_id[0]['id']
    #                                 product_attribute_value_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
    #                                 product_aging_line_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
    #                                 product_categ_1_domain = [('nhcl_id', '=', line.categ_1.nhcl_id)]
    #                                 product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
    #                                 product_categ_1_data = requests.get(product_categ_1_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_2_domain = [('nhcl_id', '=', line.categ_2.nhcl_id)]
    #                                 product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
    #                                 product_categ_2_data = requests.get(product_categ_2_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_3_domain = [('nhcl_id', '=', line.categ_3.nhcl_id)]
    #                                 product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
    #                                 product_categ_3_data = requests.get(product_categ_3_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_4_domain = [('nhcl_id', '=', line.categ_4.nhcl_id)]
    #                                 product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
    #                                 product_categ_4_data = requests.get(product_categ_4_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_5_domain = [('nhcl_id', '=', line.categ_5.nhcl_id)]
    #                                 product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
    #                                 product_categ_5_data = requests.get(product_categ_5_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_6_domain = [('nhcl_id', '=', line.categ_6.nhcl_id)]
    #                                 product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
    #                                 product_categ_6_data = requests.get(product_categ_6_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_categ_7_domain = [('nhcl_id', '=', line.categ_7.nhcl_id)]
    #                                 product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
    #                                 product_categ_7_data = requests.get(product_categ_7_store_url,
    #                                                                     headers=headers_source).json()
    #                                 product_descrip_1_domain = [('nhcl_id', '=', line.descrip_1.nhcl_id)]
    #                                 product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
    #                                 product_descrip_1_data = requests.get(product_descrip_1_store_url,
    #                                                                       headers=headers_source).json()
    #                                 product_descrip_2_domain = [('nhcl_id', '=', line.descrip_2.nhcl_id)]
    #                                 product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
    #                                 product_descrip_2_data = requests.get(product_descrip_2_store_url,
    #                                                                       headers=headers_source).json()
    #                                 product_descrip_3_domain = [('nhcl_id', '=', line.descrip_3.nhcl_id)]
    #                                 product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
    #                                 product_descrip_3_data = requests.get(product_descrip_3_store_url,
    #                                                                       headers=headers_source).json()
    #                                 product_descrip_4_domain = [('nhcl_id', '=', line.descrip_4.nhcl_id)]
    #                                 product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
    #                                 product_descrip_4_data = requests.get(product_descrip_4_store_url,
    #                                                                       headers=headers_source).json()
    #                                 product_descrip_5_domain = [('nhcl_id', '=', line.descrip_5.nhcl_id)]
    #                                 product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
    #                                 product_descrip_5_data = requests.get(product_descrip_5_store_url,
    #                                                                       headers=headers_source).json()
    #                                 product_descrip_6_domain = [('nhcl_id', '=', line.descrip_6.nhcl_id)]
    #                                 product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
    #                                 product_descrip_6_data = requests.get(product_descrip_6_store_url,
    #                                                                       headers=headers_source).json()
    #
    #                                 product_categ_1_ids = product_categ_1_data.get("data")
    #                                 if product_categ_1_ids:
    #                                     product_categ_1_id = product_categ_1_ids[0]["id"]
    #                                 # else:
    #                                 #     ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
    #                                 #                                                        'add', 'failure',
    #                                 #                                                        f"{self.name, self.move_line_ids_without_package.categ_1.name}Category 1 Not found")
    #                                 product_categ_2_ids = product_categ_2_data.get("data")
    #                                 if product_categ_2_ids:
    #                                     product_categ_2_id = product_categ_2_ids[0]["id"]
    #                                 product_categ_3_ids = product_categ_3_data.get("data")
    #                                 if product_categ_3_ids:
    #                                     product_categ_3_id = product_categ_3_ids[0]["id"]
    #                                 product_categ_4_ids = product_categ_4_data.get("data")
    #                                 if product_categ_4_ids:
    #                                     product_categ_4_id = product_categ_4_ids[0]["id"]
    #                                 product_categ_5_ids = product_categ_5_data.get("data")
    #                                 if product_categ_5_ids:
    #                                     product_categ_5_id = product_categ_5_ids[0]["id"]
    #                                 product_categ_6_ids = product_categ_6_data.get("data")
    #                                 if product_categ_6_ids:
    #                                     product_categ_6_id = product_categ_6_ids[0]["id"]
    #                                 product_categ_7_ids = product_categ_7_data.get("data")
    #                                 if product_categ_7_ids:
    #                                     product_categ_7_id = product_categ_7_ids[0]["id"]
    #                                 product_descrip_1_ids = product_descrip_1_data.get("data")
    #                                 if product_descrip_1_ids:
    #                                     product_descrip_1_id = product_descrip_1_ids[0]["id"]
    #                                 product_descrip_2_ids = product_descrip_2_data.get("data")
    #                                 if product_descrip_2_ids:
    #                                     product_descrip_2_id = product_descrip_2_ids[0]["id"]
    #                                 product_descrip_3_ids = product_descrip_3_data.get("data")
    #                                 if product_descrip_3_ids:
    #                                     product_descrip_3_id = product_descrip_3_ids[0]["id"]
    #                                 product_descrip_4_ids = product_descrip_4_data.get("data")
    #                                 if product_descrip_4_ids:
    #                                     product_descrip_4_id = product_descrip_4_ids[0]["id"]
    #                                 product_descrip_5_ids = product_descrip_5_data.get("data")
    #                                 if product_descrip_5_ids:
    #                                     product_descrip_5_id = product_descrip_5_ids[0]["id"]
    #                                 product_descrip_6_ids = product_descrip_6_data.get("data")
    #                                 if product_descrip_6_ids:
    #                                     product_descrip_6_id = product_descrip_6_ids[0]["id"]
    #                                 mr_price = 0.0
    #                                 if line.mr_price:
    #                                     mr_price = line.mr_price
    #                                 cost_price = line.cost_price
    #                                 print("cost_price", cost_price)
    #                                 move_line_vals = {
    #                                     "product_id": product_id,
    #                                     "cost_price": cost_price,
    #                                     "quantity": line.quantity,
    #                                     "location_id": location_id,
    #                                     "location_dest_id": dest_location_id,
    #                                     "lot_name": line.lot_id.name if line.lot_id else None,
    #                                     'internal_ref_lot': line.internal_ref_lot,
    #                                     'rs_price': line.rs_price if line.rs_price else 0,
    #                                     'type_product': line.type_product,
    #                                     'segment': line.segment,
    #                                     'categ_1': product_categ_1_id if line.categ_1 else False,
    #                                     'categ_2': product_categ_2_id if line.categ_2 else False,
    #                                     'categ_3': product_categ_3_id if line.categ_3 else False,
    #                                     'categ_4': product_categ_4_id if line.categ_4 else False,
    #                                     'categ_5': product_categ_5_id if line.categ_5 else False,
    #                                     'categ_6': product_categ_6_id if line.categ_6 else False,
    #                                     'categ_7': product_categ_7_id if line.categ_7 else False,
    #                                     'descrip_1': product_descrip_1_id if line.descrip_1 else False,
    #                                     'descrip_2': product_descrip_2_id if line.descrip_2 else False,
    #                                     'descrip_3': product_descrip_3_id if line.descrip_3 else False,
    #                                     'descrip_4': product_descrip_4_id if line.descrip_4 else False,
    #                                     'descrip_5': product_descrip_5_id if line.descrip_5 else False,
    #                                     'descrip_6': product_descrip_6_id if line.descrip_6 else False,
    #                                 }
    #                                 stock_detail_lines.append((0, 0, move_line_vals))
    #                                 print("move_line_vals", move_line_vals)
    #                             if order.company_type == 'same':
    #                                 print("ytfiygiyiyvyiv", partner_id, dest_location_id, location_id,
    #                                       stock_detail_lines)
    #                                 stock_picking_data = {
    #                                     'partner_id': partner_id,
    #                                     'picking_type_id': picking_type[0]["id"],
    #                                     'origin': order.name,
    #                                     'return_counter': "RF Counter",
    #                                     'location_id': location_id,
    #                                     'location_dest_id': dest_location_id,
    #                                     'company_id': company_id,
    #                                     'stock_type': 'pos_exchange',
    #                                     'company_type': order.company_type,
    #                                     'nhcl_store_delivery': True,
    #                                     'move_line_ids_without_package': stock_detail_lines,
    #
    #                                 }
    #                             else:  # For "other store"
    #                                 # other_store_url = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search?domain=[('nhcl_store_name','=', '{order.store_name}')]"
    #                                 # other_store_data = requests.get(other_store_url, headers=headers_source).json()
    #                                 # other_store_id = other_store_data.get("data", [])
    #                                 #
    #                                 # if not other_store_id:
    #                                 #     logging.warning(
    #                                 #         f"Other store {order.store_name.name} not found in HO. Skipping order {order.name}.")
    #                                 #     continue  # Skip this order and move to the next one
    #                                 #
    #                                 # other_store_id = other_store_id[0]["id"]
    #
    #                                 stock_picking_data = {
    #                                     'partner_id': partner_id,
    #                                     'picking_type_id': picking_type[0]["id"],
    #                                     'origin': order.name,
    #                                     'return_counter': "RF Counter",
    #                                     'location_id': location_id,
    #                                     'location_dest_id': dest_location_id,
    #                                     'company_id': company_id,
    #                                     'store_name': 2,
    #                                     'stock_type': 'pos_exchange',
    #                                     'company_type': order.company_type,
    #                                     'store_pos_order': order.store_pos_order,
    #                                     'nhcl_store_delivery': True,
    #                                     'move_line_ids_without_package': stock_detail_lines,
    #
    #                                 }
    #
    #                             # Create stock picking in HO
    #                             stock_picking_create_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/create"
    #                             stock_picking_create_response = requests.post(stock_picking_create_url,
    #                                                                           headers=headers_source,
    #                                                                           json=[stock_picking_data])
    #                             stock_picking_create_response.raise_for_status()
    #                             stock_picking = stock_picking_create_response.json()
    #                             if stock_picking:
    #                                 message = stock_picking.get("message", "No message provided")
    #                                 if stock_picking['success'] == True:
    #                                     order.nhcl_replication_status = True
    #                                     # order.validate_orders(deliver_order = 'exchange')
    #                                     _logger.info(
    #                                         f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                                     logging.info(
    #                                         f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
    #                                     ho_id.create_cmr_transaction_replication_log('success',
    #                                                                                  'Server Connected Successfully')
    #                                     ho_id.create_cmr_transaction_replication_log(
    #                                         'POS Customer Exchange Receipt Order',
    #                                         order.id, order.name,
    #                                         200,
    #                                         'add', 'success',
    #                                         f"Successfully created Journal Entry {order.name}")
    #
    #                                 else:
    #                                     _logger.info(
    #                                         f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
    #                                     logging.error(
    #                                         f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
    #                                     ho_id.create_cmr_transaction_replication_log('success', message)
    #                                     ho_id.create_cmr_transaction_replication_log(
    #                                         'POS Customer Exchange Receipt Order',
    #                                         order.id, order.name,
    #                                         200,
    #                                         'add', 'failure', message)
    #
    #                         else:
    #                             logging.warning(f"Skipping order {order.name}, location not 'Customers'.")
    #                 except Exception as e:
    #                     logging.error(f"Error while processing order {order.name}: {e}")
    #                     ho.create_cmr_transaction_replication_log("failure", str(e))
    #                     ho.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order', order.id,
    #                                                               order.name, 500, 'add', 'failure', str(e))
    #
    #         except Exception as e:
    #             logging.error(f"Error while processing order {order.name}: {e}")
    #             ho.create_cmr_transaction_replication_log("failure", str(e))
    #             ho.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order', order.id, order.name,
    #                                                       500, 'add', 'failure', str(e))

    def get_regular_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "return")])
                store_pos_delivery_orders = self.env['stock.picking'].search([
                    ('picking_type_id', '=', picking_type_id.id),
                    ('nhcl_replication_status', '=', False),
                    ('stock_picking_type', '=', 'return'),
                    ('state', '=', 'done')
                ])

                if store_pos_delivery_orders:
                    for order in store_pos_delivery_orders:
                        if order.stock_picking_type != "return":
                            continue

                        # --- 1. COMPANY SEARCH ---
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', order.company_id.name)]
                        company_data = requests.get(f"{company_search}?domain={company_domain}",
                                                    headers=headers_source).json()
                        company_id = company_data.get("data")

                        if not company_id:
                            error_msg = f"Company '{order.company_id.name}' not found at HO for order {order.name}."
                            ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id, order.name,
                                                                      200, 'add', 'failure', error_msg)
                            break

                        target_company_id = company_id[0]['id']

                        # --- 1.5. CHECK IF SALE ORDER ALREADY EXISTS AT HO BY ORIGIN ---
                        so_search_url = f"http://{ho_ip}:{ho_port}/api/sale.order/search"
                        so_domain = [('origin', '=', order.name), ('company_id', '=', target_company_id)]
                        so_check_data = requests.get(f"{so_search_url}?domain={so_domain}",
                                                     headers=headers_source).json()
                        existing_so = so_check_data.get("data")

                        if existing_so:
                            # If the sale order already exists at HO, sync local status and skip creation
                            order.nhcl_replication_status = True
                            order.confirm_orders()
                            continue

                        # --- 2. BULK COLLECT IDENTIFIERS ---
                        lines = order.move_line_ids_without_package
                        if not lines:
                            continue

                        product_nhcl_ids = [line.product_id.nhcl_id for line in lines if
                                            line.product_id and line.product_id.nhcl_id]
                        lot_names = [line.lot_id.name for line in lines if line.lot_id and line.lot_id.name]

                        # --- 3. BULK FETCH PRODUCTS FROM HO ---
                        product_map = {}
                        if product_nhcl_ids:
                            ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                            product_domain = [('nhcl_id', 'in', product_nhcl_ids)]
                            product_url = f"{ho_product_url}?domain={product_domain}&fields=['id','nhcl_id','name']"
                            product_data = requests.get(product_url, headers=headers_source).json()

                            for prod in product_data.get("data", []):
                                product_map[prod.get('nhcl_id')] = prod.get('id')

                        # --- 4. BULK FETCH LOTS FROM HO ---
                        lot_map = {}
                        if lot_names:
                            ho_lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                            stock_lot_domain = [('name', 'in', lot_names), ('company_id', '=', target_company_id)]
                            stock_lot_url = f"{ho_lot_url}?domain={stock_lot_domain}&fields=['id','name','product_id']"
                            stock_lot_data = requests.get(stock_lot_url, headers=headers_source).json()

                            for lot in stock_lot_data.get("data", []):
                                lot_map[lot.get('name')] = lot.get('id')

                        # --- 5. VALIDATE & BUILD LINE VALUES ---
                        skip_order = False
                        detail_sale_order = []

                        for line in lines:
                            # Validate Product Mapping
                            remote_product_id = product_map.get(line.product_id.nhcl_id)
                            if not remote_product_id:
                                error_msg = f"Product '{line.product_id.name}' (NHCL ID: {line.product_id.nhcl_id}) not found at HO for order {order.name}."
                                ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,
                                                                          order.name, 200, 'add', 'failure', error_msg)
                                skip_order = True
                                break

                            # Validate Lot Mapping (if line has a lot)
                            remote_lot_id = None
                            if line.lot_id:
                                remote_lot_id = lot_map.get(line.lot_id.name)
                                if not remote_lot_id:
                                    error_msg = f"Lot '{line.lot_id.name}' not found at HO for order {order.name}."
                                    ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,
                                                                              order.name, 200, 'add', 'failure',
                                                                              error_msg)
                                    skip_order = True
                                    break

                            sale_order_line_vals = {
                                "product_id": remote_product_id,
                                "product_uom_qty": line.quantity,
                                "price_unit": line.cost_price,
                                "branded_barcode": line.internal_ref_lot,
                            }
                            if remote_lot_id:
                                sale_order_line_vals['lot_ids'] = [(4, remote_lot_id)]

                            detail_sale_order.append((0, 0, sale_order_line_vals))

                        if skip_order:
                            break  # Skip order generation completely if any lookup validation failed

                        # --- 6. CREATE SALE ORDER HEADER & LINES ---
                        if detail_sale_order:
                            sale_order_payload = {
                                'partner_id': 1,
                                'origin': order.name,
                                'so_type': order.stock_type,
                                'nhcl_sale_type': 'regular',
                                'stock_type': order.stock_picking_type,
                                'company_id': target_company_id,
                                'nhcl_store_delivery': True,
                                'order_line': detail_sale_order,
                            }

                            sale_order_create_url = f"http://{ho_ip}:{ho_port}/api/sale.order/create"
                            sale_order_create_data = requests.post(sale_order_create_url, headers=headers_source,
                                                                   json=[sale_order_payload])
                            sale_order_create_data.raise_for_status()
                            sale_order_res = sale_order_create_data.json()

                            message = sale_order_res.get("message", "No message provided")
                            if not sale_order_res.get("success"):
                                ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,
                                                                          order.name, 200, 'add', 'failure', message)
                            else:
                                success_msg = f"Successfully created Delivery Order {order.name}"
                                ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,
                                                                          order.name, 200, 'add', 'success',
                                                                          success_msg)
                                order.nhcl_replication_status = True
                                order.confirm_orders()

            except Exception as e:
                ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,
                                                          order.name, 500, 'add', "failure",
                                                          str(e))

    def get_damage_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage")])
                store_pos_delivery_orders = self.env['stock.picking'].search([
                    ('picking_type_id', '=', picking_type_id.id),
                    ('nhcl_replication_status', '=', False),
                    ('stock_picking_type', '=', 'damage'),
                    ('state', '=', 'done')
                ])

                if store_pos_delivery_orders:
                    for order in store_pos_delivery_orders:
                        if order.stock_picking_type != "damage":
                            continue

                        # --- 1. COMPANY SEARCH ---
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', order.company_id.name)]
                        company_url = f"{company_search}?domain={company_domain}"
                        company_data = requests.get(company_url, headers=headers_source).json()
                        company_id = company_data.get("data")

                        if not company_id:
                            error_msg = f"Company '{order.company_id.name}' not found at HO for damage order {order.name}."
                            _logger.error(error_msg)
                            ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id, order.name,
                                                                      200, 'add', 'failure', error_msg)
                            continue

                        target_company_id = company_id[0]['id']

                        # --- 2. BULK COLLECT IDENTIFIERS ---
                        lines = order.move_line_ids_without_package
                        if not lines:
                            continue

                        product_nhcl_ids = [line.product_id.nhcl_id for line in lines if
                                            line.product_id and line.product_id.nhcl_id]
                        lot_names = [line.lot_id.name for line in lines if line.lot_id and line.lot_id.name]

                        # --- 3. BULK FETCH PRODUCTS FROM HO ---
                        product_map = {}
                        if product_nhcl_ids:
                            ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                            product_domain = [('nhcl_id', 'in', product_nhcl_ids)]
                            product_url = f"{ho_product_url}?domain={product_domain}&fields=['id','nhcl_id','name']"
                            product_data = requests.get(product_url, headers=headers_source).json()

                            for prod in product_data.get("data", []):
                                product_map[prod.get('nhcl_id')] = prod.get('id')

                        # --- 4. BULK FETCH LOTS FROM HO ---
                        lot_map = {}
                        if lot_names:
                            ho_lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                            stock_lot_domain = [('name', 'in', lot_names), ('company_id', '=', target_company_id)]
                            stock_lot_url = f"{ho_lot_url}?domain={stock_lot_domain}&fields=['id','name']"
                            stock_lot_data = requests.get(stock_lot_url, headers=headers_source).json()

                            for lot in stock_lot_data.get("data", []):
                                lot_map[lot.get('name')] = lot.get('id')

                        # --- 5. VALIDATE & BUILD LINE VALUES ---
                        skip_order = False
                        detail_sale_order = []

                        for line in lines:
                            # Validate Product
                            remote_product_id = product_map.get(line.product_id.nhcl_id)
                            if not remote_product_id:
                                error_msg = f"Product '{line.product_id.name}' (NHCL ID: {line.product_id.nhcl_id}) not found at HO for damage order {order.name}."
                                _logger.error(error_msg)
                                ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id, order.name,
                                                                          200, 'add', 'failure', error_msg)
                                skip_order = True
                                break

                            # Validate Lot (if line has a lot)
                            remote_lot_id = None
                            if line.lot_id:
                                remote_lot_id = lot_map.get(line.lot_id.name)
                                if not remote_lot_id:
                                    error_msg = f"Lot '{line.lot_id.name}' not found at HO for damage order {order.name}."
                                    _logger.error(error_msg)
                                    ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id,
                                                                              order.name, 200, 'add', 'failure',
                                                                              error_msg)
                                    skip_order = True
                                    break

                            sale_order_line_vals = {
                                "product_id": remote_product_id,
                                "product_uom_qty": line.quantity,
                                "price_unit": line.cost_price,
                            }
                            if remote_lot_id:
                                sale_order_line_vals['lot_ids'] = [(4, remote_lot_id)]

                            detail_sale_order.append((0, 0, sale_order_line_vals))

                        if skip_order:
                            continue  # Skip creation for this order entirely if any reference is missing

                        # --- 6. CREATE SALE ORDER HEADER & LINES WITH ONE PAYLOAD ---
                        if detail_sale_order:
                            sale_order_payload = {
                                'partner_id': 1,
                                'origin': order.name,
                                'so_type': order.stock_type,
                                'nhcl_sale_type': 'regular',
                                'stock_type': order.stock_picking_type,
                                'company_id': target_company_id,
                                'nhcl_store_delivery': True,
                                'order_line': detail_sale_order,
                            }

                            sale_order_create_url = f"http://{ho_ip}:{ho_port}/api/sale.order/create"
                            sale_order_create_data = requests.post(sale_order_create_url, headers=headers_source,
                                                                   json=[sale_order_payload])
                            sale_order_create_data.raise_for_status()
                            sale_order_res = sale_order_create_data.json()

                            message = sale_order_res.get("message", "No message provided")
                            if not sale_order_res.get("success"):
                                _logger.error(f"Failed to create Damage Delivery Order {order.name}. Error: {message}")
                                ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id, order.name,
                                                                          200, 'add', 'failure', message)
                            else:
                                success_msg = f"Successfully created Damage Delivery Order {order.name}"
                                _logger.info(success_msg)
                                ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id, order.name,
                                                                          200, 'add', 'success', success_msg)
                                order.nhcl_replication_status = True
                                order.confirm_orders()

            except Exception as e:
                ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id, order.name, 500, 'add',
                                                          "failure",
                                                          str(e))

    def get_return_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "return")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
                     ('stock_picking_type', '=', 'return'),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_pos_delivery_orders:
                    for order in self:
                        if order.stock_picking_type == "return":
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            picking_type_domain = [('stock_picking_type', '=', "return"),
                                                   ('company_id', '=', company_id[0]['id'])]
                            picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                            picking_type_data = requests.get(picking_type_url,
                                                             headers=headers_source).json()
                            picking_type = picking_type_data.get("data")
                            ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            location_domain = [('complete_name', '=', order.location_id.complete_name),
                                               ("active", "!=", False),
                                               ('usage', '=', 'internal'), ('company_id', '=', company_id[0]['id'])]
                            location_url = f"{ho_location_url}?domain={location_domain}"
                            location_data = requests.get(location_url,
                                                         headers=headers_source).json()
                            location_id = location_data.get("data")
                            print('source', location_id)
                            store_location_dest_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            dest_location_domain = [('complete_name', '=', order.location_dest_id.complete_name),
                                                    ("active", "!=", False),

                                                    ]
                            dest_location_url = f"{store_location_dest_url}?domain={dest_location_domain}"
                            dest_location_data = requests.get(dest_location_url,
                                                              headers=headers_source).json()
                            dest_location = dest_location_data.get("data")
                            ho_transporter_id = False
                            ho_transporter_route_id = False
                            if order.transpoter_id:
                                ho_transporter_search_url = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/search"
                                ho_transporter_domain = [('nhcl_id', '=', order.transpoter_id.nhcl_id)]
                                ho_transporter_url = f"{ho_transporter_search_url}?domain={ho_transporter_domain}"
                                ho_transporter_data = requests.get(ho_transporter_url,
                                                                   headers=headers_source).json()
                                if ho_transporter_data.get("data"):
                                    ho_transporter = ho_transporter_data.get("data")[0]
                                    ho_transporter_id = ho_transporter.get('id')
                            if order.transpoter_route_id:
                                ho_transporter_route_search_url = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/search"
                                ho_transporter_route_domain = [('nhcl_id', '=', order.transpoter_route_id.nhcl_id)]
                                ho_transporter_route_url = f"{ho_transporter_route_search_url}?domain={ho_transporter_route_domain}"
                                ho_transporter_route_data = requests.get(ho_transporter_route_url,
                                                                         headers=headers_source).json()
                                if ho_transporter_route_data.get("data"):
                                    ho_transporter_route = ho_transporter_route_data.get("data")[0]
                                    ho_transporter_route_id = ho_transporter_route.get('id')
                            barcode_lines = []
                            for rec in order.stock_picking_delivery_ids:
                                barcode_data = {
                                    'serial_no': rec.serial_no,
                                    'barcode': rec.barcode,
                                    'sequence': rec.sequence,
                                    # 'lr_number': rec.lr_number,
                                }
                                barcode_lines.append(barcode_data)
                                print("********", barcode_lines)
                                # barcode_lines.append((0, 0, barcode_data))
                            stock_picking_data = {
                                'picking_type_id': picking_type[0]['id'],
                                'origin': order.name,
                                'stock_type': order.stock_type,
                                'stock_picking_type': order.stock_picking_type,
                                'location_id': location_id[0]['id'] if location_id else False,
                                'location_dest_id': dest_location[0]['id'] if dest_location else False,
                                'company_id': location_id[0]['company_id'][0]['id'] if company_id else False,
                                'move_type': 'direct',
                                'state': 'done',
                                'nhcl_store_delivery': True,
                                'lr_number': order.lr_number if order.lr_number else None,
                                'vehicle_number': order.vehicle_number if order.vehicle_number else None,
                                'driver_name': order.driver_name if order.driver_name else None,
                                'no_of_parcel': order.no_of_parcel if order.no_of_parcel else None,
                                'nhcl_tracking_number': order.tracking_number,
                                'transpoter_id': ho_transporter_id,
                                'transpoter_route_id': ho_transporter_route_id,
                                'stock_picking_delivery_ids': barcode_lines,
                            }
                            stock_picking_search = f"http://{ho_ip}:{ho_port}/api/stock.picking/create"
                            stock_picking_data = requests.post(stock_picking_search,
                                                               headers=headers_source, json=[stock_picking_data])
                            stock_picking_data.raise_for_status()
                            # Access the JSON content from the response
                            stock_picking = stock_picking_data.json()
                            print(stock_picking)
                            # picking_id = stock_picking.get("data")
                            # Creating stock move lines
                            for line in order.move_line_ids_without_package:
                                product = line.product_id
                                product_domain = [('nhcl_id', '=', product.nhcl_id)]
                                ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                                product_url = f"{ho_product_url}?domain={product_domain}"
                                product_data = requests.get(product_url,
                                                            headers=headers_source).json()
                                product_id = product_data.get("data")
                                if line and line.lot_id:
                                    lot_name = line.lot_id.name
                                else:
                                    lot_name = None
                                print(stock_picking.get("create_id"))
                                if line:
                                    move_line_vals = {
                                        "picking_id": stock_picking.get("create_id"),
                                        "product_id": product_id[0]['id'],
                                        "quantity": line.quantity,
                                        "location_id": location_id[0]['id'],
                                        "location_dest_id": dest_location[0]["id"],
                                        "lot_name": lot_name,
                                    }
                                    print(move_line_vals)
                                    stock_move_line_search = f"http://{ho_ip}:{ho_port}/api/stock.move.line/create"
                                    stock_move_line_data = requests.post(stock_move_line_search,
                                                                         headers=headers_source,
                                                                         json=[move_line_vals])
                                    stock_move_line_data.raise_for_status()
                                    # Access the JSON content from the response
                                    stock_move_line = stock_move_line_data.json()
                                    move_line = stock_move_line.get("data")
                            print('stock_picking', stock_picking)
                            message = stock_picking.get("message", "No message provided")
                            if stock_picking.get("success") == False:
                                _logger.info(
                                    f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                ho.create_cmr_transaction_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return Delivery Order',
                                                                          order.id, order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return Delivery Order', order.id, order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                order.nhcl_replication_status = True


            except Exception as e:
                ho.create_cmr_transaction_replication_log("failure", e)

    # def store_damage_transaction(self):
    #     self.env['nhcl.initiated.status.log'].create(
    #         {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
    #          'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Main-Damage Transaction-Job', 'nhcl_status': 'success',
    #          'nhcl_details_status': 'Function Triggered'})
    #     # self.get_main_damage_delivery_orders()
    #     # self.get_damage_main_delivery_orders()
    #     # self.get_regular_delivery_orders()
    #     # self.get_regular_batch_delivery_orders()
    #     # self.get_damage_delivery_orders()
    #     # self.get_damage_batch_delivery_orders()
    #     # self.get_pos_customer_exchange_recipt_orders()
    #     # self.get_return_main_delivery_orders()
    #     self.get_return_delivery_orders()
    #     self.get_return_batch_delivery_orders()
    #     self.env['nhcl.initiated.status.log'].create(
    #         {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
    #          'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Main-Damage Transaction-Job', 'nhcl_status': 'success',
    #          'nhcl_details_status': 'Function Completed'})


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    warning_message = fields.Char(compute='_compute_warning_message')
    delivery_count = fields.Integer('Delivery Count', copy=False)

    def action_confirm(self):
        if self.delivery_count != len(self.picking_ids) and self.stock_picking_type == 'receipt':
            raise ValidationError(
                _("You are not allowed to confirm this record, because some transactions are not created from HO."))
        else:
            res = super().action_confirm()
            return res

    def replace_unavailable_serials(self):
        StockMoveLine = self.env['stock.move.line']
        StockQuant = self.env['stock.quant']

        # ---------------------------------------------------------
        # HELPER: NUMERIC PART OF SERIAL
        # P5636564 -> 5636564
        # ---------------------------------------------------------
        def serial_number(name):
            m = re.search(r'(\d+)$', name or '')
            return int(m.group(1)) if m else 0

        # ---------------------------------------------------------
        # HELPER: MOVE LINE QTY
        # ---------------------------------------------------------
        def move_line_qty(ml):
            if 'quantity' in ml._fields:
                return ml.quantity or 0.0

            if 'qty_done' in ml._fields:
                return ml.qty_done or 0.0

            return 0.0

        # ---------------------------------------------------------
        # PROCESS EACH BATCH
        # ---------------------------------------------------------
        for batch in self:

            company_id = batch.company_id.id

            # -----------------------------------------------------
            # SERIAL TRACKED + BRAND PRODUCTS ONLY
            # -----------------------------------------------------
            move_lines = batch.picking_ids.move_line_ids.filtered(
                lambda ml:
                ml.product_id.tracking == 'serial'
                and ml.lot_id
                and ml.lot_id.type_product == 'brand'
            )

            if not move_lines:
                continue

            current_move_line_ids = set(move_lines.ids)

            # =====================================================
            # IMPORTANT
            #
            # RESERVED IS FOR THE WHOLE BATCH.
            #
            # Key:
            #     product_id + lot_id
            #
            # Once a serial is accepted/replaced anywhere
            # in this batch, it cannot be used again.
            # =====================================================
            reserved = set()

            # -----------------------------------------------------
            # SORT CURRENT LINES
            # -----------------------------------------------------
            sorted_lines = sorted(
                move_lines,
                key=lambda x: (
                    x.product_id.id,
                    serial_number(x.lot_id.name),
                    x.picking_id.id,
                    x.id,
                )
            )

            # -----------------------------------------------------
            # PROCESS CURRENT BATCH
            # -----------------------------------------------------
            for ml in sorted_lines:

                product = ml.product_id
                lot = ml.lot_id

                source_location = ml.picking_id.location_id

                if not source_location:
                    continue

                source_location_id = source_location.id
                current_ref = lot.ref

                # =================================================
                # BATCH-WIDE DUPLICATE CHECK
                # =================================================
                reserved_key = (
                    product.id,
                    lot.id,
                )

                duplicate_in_batch = reserved_key in reserved

                # =================================================
                # CURRENT SERIAL:
                # INWARD / OUTWARD AGAINST SOURCE LOCATION
                # =================================================
                serial_history = StockMoveLine.sudo().search([
                    (
                        'id',
                        'not in',
                        list(current_move_line_ids)
                    ),
                    ('product_id', '=', product.id),
                    ('lot_id', '=', lot.id),
                    ('company_id', '=', company_id),
                    ('state', '!=', 'cancel'),
                ])

                inward_qty = 0.0
                outward_qty = 0.0

                for hist_ml in serial_history:

                    qty = move_line_qty(hist_ml)

                    # Serial entered source location
                    if (
                            hist_ml.location_dest_id
                            and hist_ml.location_dest_id.id
                            == source_location_id
                    ):
                        inward_qty += qty

                    # Serial left source location
                    if (
                            hist_ml.location_id
                            and hist_ml.location_id.id
                            == source_location_id
                    ):
                        outward_qty += qty

                # =================================================
                # CURRENT SERIAL ON-HAND IN SOURCE LOCATION
                # =================================================
                current_quants = StockQuant.sudo().search([
                    ('product_id', '=', product.id),
                    ('lot_id', '=', lot.id),
                    ('company_id', '=', company_id),
                    ('location_id', '=', source_location_id),
                ])

                onhand_qty = sum(
                    current_quants.mapped('quantity')
                ) if current_quants else 0.0

                # =================================================
                # CURRENT SERIAL AVAILABLE
                # =================================================
                serial_available = (
                        inward_qty > outward_qty
                        and onhand_qty > 0
                )

                # =================================================
                # ACCEPT CURRENT SERIAL
                #
                # Conditions:
                # 1. Inward > Outward
                # 2. On Hand > 0
                # 3. Not already used anywhere in THIS BATCH
                # =================================================
                if (
                        serial_available
                        and not duplicate_in_batch
                ):
                    reserved.add(reserved_key)
                    continue

                # =================================================
                # CURRENT SERIAL NEEDS REPLACEMENT
                # =================================================
                current_serial = serial_number(lot.name)

                # =================================================
                # GET POSSIBLE SERIALS FROM CURRENT
                # PICKING SOURCE LOCATION
                # =================================================
                candidate_quants = StockQuant.sudo().search([
                    ('product_id', '=', product.id),
                    ('company_id', '=', company_id),
                    ('location_id', '=', source_location_id),
                    ('lot_id', '!=', False),
                    ('lot_id.type_product', '=', 'brand'),
                    ('quantity', '>', 0),
                ])

                # =================================================
                # SAME PRODUCT + SAME BARCODE/REF
                # =================================================
                candidate_lots = candidate_quants.mapped(
                    'lot_id'
                ).filtered(
                    lambda candidate:
                    candidate.ref == current_ref
                )

                # =================================================
                # LOWEST SERIAL FIRST
                # =================================================
                candidate_lots = candidate_lots.sorted(
                    key=lambda candidate:
                    serial_number(candidate.name)
                )

                replacement = False

                replacement_inward = 0.0
                replacement_outward = 0.0
                replacement_onhand = 0.0

                # =================================================
                # FIND NEXT AVAILABLE SERIAL
                # =================================================
                for candidate in candidate_lots:

                    # ---------------------------------------------
                    # Never select current serial itself
                    # ---------------------------------------------
                    if candidate.id == lot.id:
                        continue

                    candidate_serial = serial_number(
                        candidate.name
                    )

                    # ---------------------------------------------
                    # Must be higher than current serial
                    # ---------------------------------------------
                    if candidate_serial <= current_serial:
                        continue

                    # =============================================
                    # CRITICAL:
                    #
                    # SERIAL CANNOT ALREADY HAVE BEEN USED
                    # ANYWHERE IN CURRENT BATCH.
                    # =============================================
                    candidate_reserved_key = (
                        product.id,
                        candidate.id,
                    )

                    if candidate_reserved_key in reserved:
                        continue

                    # =============================================
                    # ALSO CHECK WHETHER CANDIDATE ALREADY EXISTS
                    # IN ANOTHER CURRENT BATCH MOVE LINE.
                    #
                    # This prevents assigning P5636564 as a
                    # replacement when another line in this batch
                    # already originally contains P5636564.
                    # =============================================
                    candidate_already_in_batch = any(
                        other_ml.id != ml.id
                        and other_ml.product_id.id == product.id
                        and other_ml.lot_id.id == candidate.id
                        for other_ml in move_lines
                    )

                    if candidate_already_in_batch:
                        continue

                    # =============================================
                    # CANDIDATE HISTORICAL MOVEMENT
                    # AGAINST SAME SOURCE LOCATION
                    # =============================================
                    candidate_history = StockMoveLine.sudo().search([
                        (
                            'id',
                            'not in',
                            list(current_move_line_ids)
                        ),
                        ('product_id', '=', product.id),
                        ('lot_id', '=', candidate.id),
                        ('company_id', '=', company_id),
                        ('state', '!=', 'cancel'),
                    ])

                    candidate_inward = 0.0
                    candidate_outward = 0.0

                    for hist_ml in candidate_history:

                        qty = move_line_qty(hist_ml)

                        # Entered source location
                        if (
                                hist_ml.location_dest_id
                                and hist_ml.location_dest_id.id
                                == source_location_id
                        ):
                            candidate_inward += qty

                        # Left source location
                        if (
                                hist_ml.location_id
                                and hist_ml.location_id.id
                                == source_location_id
                        ):
                            candidate_outward += qty

                    # =============================================
                    # CANDIDATE ON-HAND IN SAME SOURCE LOCATION
                    # =============================================
                    candidate_quant_rows = StockQuant.sudo().search([
                        ('product_id', '=', product.id),
                        ('lot_id', '=', candidate.id),
                        ('company_id', '=', company_id),
                        ('location_id', '=', source_location_id),
                    ])

                    candidate_onhand = sum(
                        candidate_quant_rows.mapped('quantity')
                    ) if candidate_quant_rows else 0.0

                    # ---------------------------------------------
                    # Must physically exist
                    # ---------------------------------------------
                    if candidate_onhand <= 0:
                        continue

                    # ---------------------------------------------
                    # Inward must be greater than outward
                    # ---------------------------------------------
                    if candidate_inward <= candidate_outward:
                        continue

                    # =============================================
                    # VALID REPLACEMENT
                    # =============================================
                    replacement = candidate

                    replacement_inward = candidate_inward
                    replacement_outward = candidate_outward
                    replacement_onhand = candidate_onhand

                    break

                # =================================================
                # NO REPLACEMENT FOUND
                # =================================================
                if not replacement:

                    if duplicate_in_batch:
                        reason = (
                            "Current Serial already used "
                            "elsewhere in this batch"
                        )

                    elif onhand_qty <= 0:
                        reason = (
                            "No On Hand Qty in Source Location"
                        )

                    elif inward_qty <= outward_qty:
                        reason = (
                            "Inward Qty is not greater than "
                            "Outward Qty in Source Location"
                        )

                    else:
                        reason = (
                            "No unused higher serial available "
                            "for same Barcode/Ref in Source Location"
                        )

                    raise ValidationError(
                        _(
                            "No next available serial found.\n"
                            "Product: %s\n"
                            "Barcode/Ref: %s\n"
                            "Source Location: %s\n"
                            "Current Serial: %s\n"
                            "Inward Qty: %s\n"
                            "Outward Qty: %s\n"
                            "On Hand Qty: %s\n"
                            "Reason: %s"
                        ) % (
                            product.display_name,
                            current_ref or '',
                            source_location.display_name,
                            lot.name,
                            inward_qty,
                            outward_qty,
                            onhand_qty,
                            reason,
                        )
                    )

                # =================================================
                # REPLACE SERIAL
                # =================================================
                ml.lot_id = replacement.id

                # =================================================
                # IMMEDIATELY RESERVE REPLACEMENT FOR WHOLE BATCH
                #
                # Example:
                # P5636564 selected here
                #
                # It can NEVER be selected again for another
                # line/picking within this batch.
                # =================================================
                reserved.add((
                    product.id,
                    replacement.id,
                ))

        return True

    def action_done(self):
        for rec in self:
            if rec.stock_picking_type in ['return', 'damage', 'pos_order']:
                rec.replace_unavailable_serials()
        return super().action_done()

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.nhcl_replication_status == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'


    def get_regular_batch_delivery_orders(self):
        ho_stores = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '=', 'ho'),
            ('nhcl_active', '=', True)
        ])

        picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', 'return')], limit=1)
        if not picking_type_id:
            return

        for ho in ho_stores:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                batches = self.env['stock.picking.batch'].search([
                    ('picking_type_id', '=', picking_type_id.id),
                    ('nhcl_replication_status', '=', False),
                    ('state', '=', 'done')
                ])

                if not batches:
                    continue

                for order in batches:
                    try:
                        # 1. Fetch Company Data Safely
                        company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                        company_domain = [('name', '=', order.company_id.name)]
                        company_url = f"{company_search}?domain={company_domain}&fields=['id','name']"

                        try:
                            company_res = requests.get(company_url, headers=headers_source, timeout=10).json()
                            company_data_list = company_res.get("data")
                        except Exception as e:
                            ho.create_cmr_transaction_replication_log(
                                'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                f"API error fetching company '{order.company_id.name}': {str(e)}"
                            )
                            continue

                        if not company_data_list:
                            ho.create_cmr_transaction_replication_log(
                                'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                f"Company '{order.company_id.name}' not found on HO server."
                            )
                            continue

                        company_id = company_data_list[0]

                        batch_picking_ids = []
                        failed_picking = False

                        for picking in order.picking_ids:
                            picking.get_regular_delivery_orders()
                            picking.confirm_orders()

                            # 2. Fetch Sale Order safely
                            ho_sale_order_url = f"http://{ho_ip}:{ho_port}/api/sale.order/search"
                            ho_sale_order_domain = [('origin', '=', picking.name),
                                                    ('company_id', '=', company_id.get('id'))]
                            sale_order_url = f"{ho_sale_order_url}?domain={ho_sale_order_domain}&fields=['id','name']"

                            try:
                                sale_order_res = requests.get(sale_order_url, headers=headers_source, timeout=10).json()
                                sale_order_data = sale_order_res.get("data")
                            except Exception as e:
                                failed_picking = True
                                ho.create_cmr_transaction_replication_log(
                                    'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                    f"API error fetching sale order for picking {picking.name}: {str(e)}"
                                )
                                break

                            if not sale_order_data:
                                failed_picking = True
                                ho.create_cmr_transaction_replication_log(
                                    'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                    f"Sale Order not found on HO for picking reference: {picking.name}"
                                )
                                break
                            ho_sale_order = sale_order_data[0]

                            # 3. Fetch Stock Picking safely
                            ho_delivery_search_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/search"
                            ho_delivery_domain = [('origin', '=', ho_sale_order.get('name')),
                                                  ('company_id', '=', company_id.get('id'))]
                            ho_delivery_url = f"{ho_delivery_search_url}?domain={ho_delivery_domain}&fields=['id','name']"

                            try:
                                delivery_res = requests.get(ho_delivery_url, headers=headers_source, timeout=10).json()
                                delivery_data = delivery_res.get("data")
                            except Exception as e:
                                failed_picking = True
                                ho.create_cmr_transaction_replication_log(
                                    'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                    f"API error fetching stock picking for sale order {ho_sale_order.get('name')}: {str(e)}"
                                )
                                break

                            if not delivery_data:
                                failed_picking = True
                                ho.create_cmr_transaction_replication_log(
                                    'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                    f"Stock picking delivery not found on HO for sale order: {ho_sale_order.get('name')}"
                                )
                                break
                            ho_sale_order_delivery = delivery_data[0]

                            transporter_update_id = ho_sale_order_delivery.get('id')
                            batch_picking_ids.append(transporter_update_id)

                            # Fetch Transporter & Route IDs if applicable
                            ho_transporter_id = False
                            ho_transporter_route_id = False

                            if picking.transpoter_id:
                                try:
                                    tr_url = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/search?domain=[('nhcl_id', '=', {picking.transpoter_id.nhcl_id})]"
                                    tr_res = requests.get(tr_url, headers=headers_source, timeout=10).json()
                                    if tr_res.get("data"):
                                        ho_transporter_id = tr_res.get("data")[0].get('id')
                                except Exception as e:
                                    ho.create_cmr_transaction_replication_log(
                                        'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                        f"Failed to fetch transporter mapping: {str(e)}"
                                    )

                            if picking.transpoter_route_id:
                                try:
                                    rt_url = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/search?domain=[('nhcl_id', '=', {picking.transpoter_route_id.nhcl_id})]"
                                    rt_res = requests.get(rt_url, headers=headers_source, timeout=10).json()
                                    if rt_res.get("data"):
                                        ho_transporter_route_id = rt_res.get("data")[0].get('id')
                                except Exception as e:
                                    ho.create_cmr_transaction_replication_log(
                                        'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                        f"Failed to fetch transporter route mapping: {str(e)}"
                                    )

                            barcode_lines = [(0, 0, {
                                'serial_no': rec.serial_no,
                                'barcode': rec.barcode,
                                'sequence': rec.sequence,
                            }) for rec in picking.stock_picking_delivery_ids]

                            transport_data = {
                                'stock_picking_type': picking.stock_picking_type,
                                'lr_number': picking.lr_number or None,
                                'vehicle_number': picking.vehicle_number or None,
                                'driver_name': picking.driver_name or None,
                                'no_of_parcel': picking.no_of_parcel or None,
                                'nhcl_tracking_number': picking.tracking_number,
                                'transpoter_id': ho_transporter_id,
                                'transpoter_route_id': ho_transporter_route_id,
                                'stock_picking_delivery_ids': barcode_lines,
                            }

                            # Update individual stock picking with transport data
                            try:
                                update_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/{transporter_update_id}"
                                resp = requests.put(update_url, headers=headers_source, json=transport_data, timeout=10)
                                resp.raise_for_status()
                            except Exception as e:
                                ho.create_cmr_transaction_replication_log(
                                    'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                    f"Failed to update stock picking transport data: {str(e)}"
                                )

                        if failed_picking:
                            continue

                        # 4. Create Batch Order on HO
                        store_batch_data = {
                            'name': order.name,
                            "user_id": 2,
                            "nhcl_company": False,  # Removed ho_master_id reference
                            'picking_ids': batch_picking_ids,
                            'company_id': company_id.get('id'),
                        }

                        create_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                        try:
                            create_resp = requests.post(create_url, headers=headers_source, json=[store_batch_data],
                                                        timeout=10)
                            create_resp.raise_for_status()
                            res_json = create_resp.json()
                        except Exception as e:
                            ho.create_cmr_transaction_replication_log(
                                'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure',
                                f"API error creating stock picking batch: {str(e)}"
                            )
                            continue

                        message = res_json.get("message", "No message provided")
                        if not res_json.get("success", True):
                            ho.create_cmr_transaction_replication_log(
                                'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure', message
                            )
                        else:
                            ho.create_cmr_transaction_replication_log(
                                'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'success',
                                f"Successfully created Delivery Order {order.name}: {message}"
                            )
                            order.nhcl_replication_status = True

                    except Exception as e:
                        ho.create_cmr_transaction_replication_log(
                            'Regular Batch Delivery Order', order.id, order.name, 200, 'add', 'failure', str(e)
                        )
            except Exception as e:
                ho.create_cmr_transaction_replication_log(
                    'Regular Batch Delivery Order', 0, 'Store Loop Exception', 200, 'add', 'failure', str(e)
                )

    def get_damage_batch_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage")])
                store_regular_batch_delivery_orders = self.env['stock.picking.batch'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_regular_batch_delivery_orders:
                    for order in self:
                        try:
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")[0]
                            ho_master_search = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search"
                            ho_master_domain = [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)]
                            ho_master_url = f"{ho_master_search}?domain={ho_master_domain}"
                            ho_master_data = requests.get(ho_master_url, headers=headers_source).json()
                            ho_master_id = ho_master_data.get("data")[0]
                            batch = []
                            for picking in order.picking_ids:
                                picking.get_damage_delivery_orders()
                                ho_sale_order_url = f"http://{ho_ip}:{ho_port}/api/sale.order/search"
                                ho_sale_order_domain = [('origin', '=', picking.name)]
                                sale_order_url = f"{ho_sale_order_url}?domain={ho_sale_order_domain}"
                                sale_order_data = requests.get(sale_order_url,
                                                               headers=headers_source).json()
                                ho_sale_order = sale_order_data.get("data")[0]

                                ho_sale_order_delivery_search_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/search"
                                ho_sale_order_delivery_domain = [('origin', '=', ho_sale_order.get('name'))]
                                ho_sale_order_delivery_url = f"{ho_sale_order_delivery_search_url}?domain={ho_sale_order_delivery_domain}"
                                ho_sale_order_delivery_data = requests.get(ho_sale_order_delivery_url,
                                                                           headers=headers_source).json()
                                ho_sale_order_delivery = ho_sale_order_delivery_data.get("data")[0]
                                batch.append(ho_sale_order_delivery.get('id'))
                                transporter_update_id = ho_sale_order_delivery.get('id')
                                ho_transporter_id = False
                                ho_transporter_route_id = False
                                if picking.transpoter_id:
                                    ho_transporter_search_url = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/search"
                                    ho_transporter_domain = [('nhcl_id', '=', picking.transpoter_id.nhcl_id)]
                                    ho_transporter_url = f"{ho_transporter_search_url}?domain={ho_transporter_domain}"
                                    ho_transporter_data = requests.get(ho_transporter_url,
                                                                       headers=headers_source).json()
                                    ho_transporter = ho_transporter_data.get("data")[0]
                                    ho_transporter_id = ho_transporter.get('id')
                                if picking.transpoter_route_id:
                                    ho_transporter_route_search_url = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/search"
                                    ho_transporter_route_domain = [
                                        ('nhcl_id', '=', picking.transpoter_route_id.nhcl_id)]
                                    ho_transporter_route_url = f"{ho_transporter_route_search_url}?domain={ho_transporter_route_domain}"
                                    ho_transporter_route_data = requests.get(ho_transporter_route_url,
                                                                             headers=headers_source).json()
                                    ho_transporter_route = ho_transporter_route_data.get("data")[0]
                                    ho_transporter_route_id = ho_transporter_route.get('id')
                                transport_data = {
                                    'stock_picking_type': picking.stock_picking_type,
                                    'lr_number': picking.lr_number if picking.lr_number else None,
                                    'vehicle_number': picking.vehicle_number if picking.vehicle_number else None,
                                    'driver_name': picking.driver_name if picking.driver_name else None,
                                    'no_of_parcel': picking.no_of_parcel if picking.no_of_parcel else None,
                                    'nhcl_tracking_number': picking.tracking_number,
                                    'transpoter_id': ho_transporter_id,
                                    'transpoter_route_id': ho_transporter_route_id,
                                }
                                print("transport_data", transport_data)
                                try:
                                    ho_delivery_transporter_data_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/{transporter_update_id}"
                                    ho_delivery_transporter_data = requests.put(ho_delivery_transporter_data_url,
                                                                                headers=headers_source,
                                                                                json=transport_data)
                                    ho_delivery_transporter_data.raise_for_status()
                                    ho_delivery_transporter = ho_delivery_transporter_data.json()

                                except Exception as e:
                                    ho.create_cmr_transaction_replication_log("failure", e)
                            store_batch_data = {
                                'name': order.name,
                                "user_id": 2,
                                "nhcl_company": ho_master_id.get('id') if ho_master_id else False,
                                'picking_ids': batch,
                                'company_id': company_id.get('id'),

                            }
                            print("store_batch_data", store_batch_data)
                            try:
                                store_batch_order_create = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                                store_batch_order_create_data = requests.post(store_batch_order_create,
                                                                              headers=headers_source,
                                                                              json=[store_batch_data])
                                store_batch_order_create_data.raise_for_status()
                                store_batch_order = store_batch_order_create_data.json()
                                message = store_batch_order.get("message", "No message provided")
                                if store_batch_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Damage Batch Delivery Order',
                                                                              order.id, order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Damage Batch Delivery Order', order.id,
                                                                              order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                            except Exception as e:
                                ho.create_cmr_transaction_replication_log("failure", e)
                        except Exception as e:
                            ho.create_cmr_transaction_replication_log("failure", e)
            except Exception as e:
                ho.create_cmr_transaction_replication_log("failure", e)

    def get_return_batch_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "return")])
                store_regular_batch_delivery_orders = self.env['stock.picking.batch'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_regular_batch_delivery_orders:
                    for order in self:
                        try:
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")[0]
                            ho_master_search = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search"
                            ho_master_domain = [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)]
                            ho_master_url = f"{ho_master_search}?domain={ho_master_domain}"
                            ho_master_data = requests.get(ho_master_url, headers=headers_source).json()
                            ho_master_id = ho_master_data.get("data")[0]
                            batch = []
                            ho_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            ho_picking_type_domain = [('stock_picking_type', '=', "return")]
                            ho_stock_picking_type_url = f"{ho_picking_type_url}?domain={ho_picking_type_domain}"
                            sale_order_data = requests.get(ho_stock_picking_type_url,
                                                           headers=headers_source).json()
                            ho_stock_picking = sale_order_data.get("data")[0]
                            ho_stock_picking_id = ho_stock_picking.get('id')
                            for picking in order.picking_ids:
                                picking.get_return_delivery_orders()
                                ho_sale_order_delivery_search_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/search"
                                ho_sale_order_delivery_domain = [('name', '=', picking.name)]
                                ho_sale_order_delivery_url = f"{ho_sale_order_delivery_search_url}?domain={ho_sale_order_delivery_domain}"
                                ho_sale_order_delivery_data = requests.get(ho_sale_order_delivery_url,
                                                                           headers=headers_source).json()
                                if ho_sale_order_delivery_data.get("data"):
                                    ho_sale_order_delivery = ho_sale_order_delivery_data.get("data")[0]
                                    batch.append(ho_sale_order_delivery.get('id'))
                            store_batch_data = {
                                'name': order.name,
                                'picking_type_id': ho_stock_picking_id,
                                "user_id": 2,
                                "nhcl_company": ho_master_id.get('id') if ho_master_id else False,
                                'picking_ids': batch,
                                'company_id': company_id.get('id'),

                            }
                            print("store_batch_data", store_batch_data)
                            try:
                                store_batch_order_create = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                                store_batch_order_create_data = requests.post(store_batch_order_create,
                                                                              headers=headers_source,
                                                                              json=[store_batch_data])
                                store_batch_order_create_data.raise_for_status()
                                store_batch_order = store_batch_order_create_data.json()
                                message = store_batch_order.get("message", "No message provided")
                                if store_batch_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Return Batch Delivery Order',
                                                                              order.id, order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Return Batch Delivery Order', order.id,
                                                                              order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                            except Exception as e:
                                ho.create_cmr_transaction_replication_log("failure", e)
                        except Exception as e:
                            ho.create_cmr_transaction_replication_log("failure", e)
            except Exception as e:
                ho.create_cmr_transaction_replication_log("failure", e)
