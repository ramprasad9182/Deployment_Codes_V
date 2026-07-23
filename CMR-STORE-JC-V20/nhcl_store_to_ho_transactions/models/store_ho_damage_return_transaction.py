
from odoo import models,api,fields,_
import requests
import logging

from odoo.exceptions import ValidationError

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
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "main_damage")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False), ('stock_picking_type', '=', 'main_damage'),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_pos_delivery_orders:
                    for order in self:
                        if order.stock_picking_type == "main_damage":
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            picking_type_domain = [('stock_picking_type', '=', "main_damage"),
                                                   ('company_id', '=', company_id[0]['id'])]
                            picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                            picking_type_data = requests.get(picking_type_url,
                                                             headers=headers_source).json()
                            picking_type = picking_type_data.get("data")
                            ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            location_domain = [('cmr_location_type', '=', order.location_id.cmr_location_type), ("active", "!=", False),
                                               ('usage', '=', 'internal'), ('company_id', '=', company_id[0]['id'])]
                            location_url = f"{ho_location_url}?domain={location_domain}&fields=['name','id']"
                            location_data = requests.get(location_url,
                                                         headers=headers_source).json()
                            location_id = location_data.get("data")
                            print('source', location_id)
                            store_location_dest_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            dest_location_domain = [('cmr_location_type', '=', order.location_dest_id.cmr_location_type),
                                                    ("active", "!=", False),
                                                    ('usage', '=', 'internal'),
                                                    ]
                            dest_location_url = f"{store_location_dest_url}?domain={dest_location_domain}&fields=['name','id']"
                            dest_location_data = requests.get(dest_location_url,
                                                              headers=headers_source).json()
                            dest_location = dest_location_data.get("data")
                            stock_picking_data = {
                                'picking_type_id': picking_type[0]['id'],
                                'origin': order.name,
                                'stock_type': order.stock_type,
                                'stock_picking_type': order.stock_picking_type,
                                'location_id': location_id[0]['id'] if location_id else False,
                                'location_dest_id': dest_location[0]['id'] if dest_location else False,
                                'company_id': company_id[0]['id'],
                                'move_type': 'direct',
                                'state': 'done',
                                'nhcl_store_delivery': True
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

                                product_attribute_value_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                                product_aging_line_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                                product_categ_1_domain = [('nhcl_id', '=', line.categ_1.nhcl_id)]
                                product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
                                product_categ_1_data = requests.get(product_categ_1_store_url,
                                                                    headers=headers_source).json()
                                product_categ_2_domain = [('nhcl_id', '=', line.categ_2.nhcl_id)]
                                product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
                                product_categ_2_data = requests.get(product_categ_2_store_url,
                                                                    headers=headers_source).json()
                                product_categ_3_domain = [('nhcl_id', '=', line.categ_3.nhcl_id)]
                                product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
                                product_categ_3_data = requests.get(product_categ_3_store_url,
                                                                    headers=headers_source).json()
                                product_categ_4_domain = [('nhcl_id', '=', line.categ_4.nhcl_id)]
                                product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
                                product_categ_4_data = requests.get(product_categ_4_store_url,
                                                                    headers=headers_source).json()
                                product_categ_5_domain = [('nhcl_id', '=', line.categ_5.nhcl_id)]
                                product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
                                product_categ_5_data = requests.get(product_categ_5_store_url,
                                                                    headers=headers_source).json()
                                product_categ_6_domain = [('nhcl_id', '=', line.categ_6.nhcl_id)]
                                product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
                                product_categ_6_data = requests.get(product_categ_6_store_url,
                                                                    headers=headers_source).json()
                                product_categ_7_domain = [('nhcl_id', '=', line.categ_7.nhcl_id)]
                                product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
                                product_categ_7_data = requests.get(product_categ_7_store_url,
                                                                    headers=headers_source).json()
                                product_descrip_1_domain = [('nhcl_id', '=', line.descrip_1.nhcl_id)]
                                product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
                                product_descrip_1_data = requests.get(product_descrip_1_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_2_domain = [('nhcl_id', '=', line.descrip_2.nhcl_id)]
                                product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
                                product_descrip_2_data = requests.get(product_descrip_2_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_3_domain = [('nhcl_id', '=', line.descrip_3.nhcl_id)]
                                product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
                                product_descrip_3_data = requests.get(product_descrip_3_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_4_domain = [('nhcl_id', '=', line.descrip_4.nhcl_id)]
                                product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
                                product_descrip_4_data = requests.get(product_descrip_4_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_5_domain = [('nhcl_id', '=', line.descrip_5.nhcl_id)]
                                product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
                                product_descrip_5_data = requests.get(product_descrip_5_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_6_domain = [('nhcl_id', '=', line.descrip_6.nhcl_id)]
                                product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
                                product_descrip_6_data = requests.get(product_descrip_6_store_url,
                                                                      headers=headers_source).json()

                                product_categ_1_ids = product_categ_1_data.get("data")
                                if product_categ_1_ids:
                                    product_categ_1_id = product_categ_1_ids[0]["id"]
                                # else:
                                #     ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                #                                                        'add', 'failure',
                                #                                                        f"{self.name, self.move_line_ids_without_package.categ_1.name}Category 1 Not found")
                                product_categ_2_ids = product_categ_2_data.get("data")
                                if product_categ_2_ids:
                                    product_categ_2_id = product_categ_2_ids[0]["id"]
                                product_categ_3_ids = product_categ_3_data.get("data")
                                if product_categ_3_ids:
                                    product_categ_3_id = product_categ_3_ids[0]["id"]
                                product_categ_4_ids = product_categ_4_data.get("data")
                                if product_categ_4_ids:
                                    product_categ_4_id = product_categ_4_ids[0]["id"]
                                product_categ_5_ids = product_categ_5_data.get("data")
                                if product_categ_5_ids:
                                    product_categ_5_id = product_categ_5_ids[0]["id"]
                                product_categ_6_ids = product_categ_6_data.get("data")
                                if product_categ_6_ids:
                                    product_categ_6_id = product_categ_6_ids[0]["id"]
                                product_categ_7_ids = product_categ_7_data.get("data")
                                if product_categ_7_ids:
                                    product_categ_7_id = product_categ_7_ids[0]["id"]
                                product_descrip_1_ids = product_descrip_1_data.get("data")
                                if product_descrip_1_ids:
                                    product_descrip_1_id = product_descrip_1_ids[0]["id"]
                                product_descrip_2_ids = product_descrip_2_data.get("data")
                                if product_descrip_2_ids:
                                    product_descrip_2_id = product_descrip_2_ids[0]["id"]
                                product_descrip_3_ids = product_descrip_3_data.get("data")
                                if product_descrip_3_ids:
                                    product_descrip_3_id = product_descrip_3_ids[0]["id"]
                                product_descrip_4_ids = product_descrip_4_data.get("data")
                                if product_descrip_4_ids:
                                    product_descrip_4_id = product_descrip_4_ids[0]["id"]
                                product_descrip_5_ids = product_descrip_5_data.get("data")
                                if product_descrip_5_ids:
                                    product_descrip_5_id = product_descrip_5_ids[0]["id"]
                                product_descrip_6_ids = product_descrip_6_data.get("data")
                                if product_descrip_6_ids:
                                    product_descrip_6_id = product_descrip_6_ids[0]["id"]
                                mr_price = 0.0
                                if line.mr_price:
                                    mr_price = line.mr_price

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
                                        'internal_ref_lot': line.internal_ref_lot,
                                        'rs_price': line.rs_price if line.rs_price else 0,
                                        'cost_price': line.cost_price if line.cost_price else 0,
                                        'type_product': line.type_product,
                                        'segment': line.segment,
                                        'categ_1': product_categ_1_id if line.categ_1 else False,
                                        'categ_2': product_categ_2_id if line.categ_2 else False,
                                        'categ_3': product_categ_3_id if line.categ_3 else False,
                                        'categ_4': product_categ_4_id if line.categ_4 else False,
                                        'categ_5': product_categ_5_id if line.categ_5 else False,
                                        'categ_6': product_categ_6_id if line.categ_6 else False,
                                        'categ_7': product_categ_7_id if line.categ_7 else False,
                                        'descrip_1': product_descrip_1_id if line.descrip_1 else False,
                                        'descrip_2': product_descrip_2_id if line.descrip_2 else False,
                                        'descrip_3': product_descrip_3_id if line.descrip_3 else False,
                                        'descrip_4': product_descrip_4_id if line.descrip_4 else False,
                                        'descrip_5': product_descrip_5_id if line.descrip_5 else False,
                                        'descrip_6': product_descrip_6_id if line.descrip_6 else False,
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
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Main to Damage Delivery order',
                                                                          order.id,order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Main to Damage Delivery order', order.id,order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                order.nhcl_replication_status = True

                                order.validate_orders(deliver_order='main_damage')

            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def get_damage_main_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage_main")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False), ('stock_picking_type', '=', 'damage_main'),
                     ('state', '=', 'done')])
                product_categ_1_id = product_categ_2_id = False
                # Fetching delivery orders
                if store_pos_delivery_orders:
                    for order in self:
                        if order.stock_picking_type == "damage_main":
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            picking_type_domain = [('stock_picking_type', '=', "damage_main"),
                                                   ('company_id', '=', company_id[0]['id'])]
                            picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                            picking_type_data = requests.get(picking_type_url,
                                                             headers=headers_source).json()
                            picking_type = picking_type_data.get("data")
                            print("picking types",picking_type)
                            ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            location_domain = [('cmr_location_type', '=', order.location_id.cmr_location_type), ("active", "!=", False),
                                               ('usage', '=', 'internal'), ('company_id', '=', company_id[0]['id'])]
                            location_url = f"{ho_location_url}?domain={location_domain}&fields=['name','id']"
                            location_data = requests.get(location_url,
                                                         headers=headers_source).json()
                            location_id = location_data.get("data")
                            print('source', location_id)
                            store_location_dest_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            dest_location_domain = [('cmr_location_type', '=', order.location_dest_id.cmr_location_type),
                                                    ("active", "!=", False),
                                                    ('usage', '=', 'internal'),
                                                    ]
                            dest_location_url = f"{store_location_dest_url}?domain={dest_location_domain}&fields=['name','id']"
                            dest_location_data = requests.get(dest_location_url,
                                                              headers=headers_source).json()
                            dest_location = dest_location_data.get("data")
                            stock_picking_data = {
                                'picking_type_id': picking_type[0]['id'],
                                'origin': order.name,
                                'stock_type': order.stock_type,
                                'stock_picking_type': order.stock_picking_type,
                                'location_id': location_id[0]['id'] if location_id else False,
                                'location_dest_id': dest_location[0]['id'] if dest_location else False,
                                'company_id': company_id[0]['id'],
                                'move_type': 'direct',
                                'state': 'done',
                                'nhcl_store_delivery': True
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
                                product_attribute_value_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                                product_aging_line_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                                product_categ_1_domain = [('nhcl_id', '=', line.categ_1.nhcl_id)]
                                product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
                                product_categ_1_data = requests.get(product_categ_1_store_url,
                                                                    headers=headers_source).json()
                                product_categ_2_domain = [('nhcl_id', '=', line.categ_2.nhcl_id)]
                                product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
                                product_categ_2_data = requests.get(product_categ_2_store_url,
                                                                    headers=headers_source).json()
                                product_categ_3_domain = [('nhcl_id', '=', line.categ_3.nhcl_id)]
                                product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
                                product_categ_3_data = requests.get(product_categ_3_store_url,
                                                                    headers=headers_source).json()
                                product_categ_4_domain = [('nhcl_id', '=', line.categ_4.nhcl_id)]
                                product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
                                product_categ_4_data = requests.get(product_categ_4_store_url,
                                                                    headers=headers_source).json()
                                product_categ_5_domain = [('nhcl_id', '=', line.categ_5.nhcl_id)]
                                product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
                                product_categ_5_data = requests.get(product_categ_5_store_url,
                                                                    headers=headers_source).json()
                                product_categ_6_domain = [('nhcl_id', '=', line.categ_6.nhcl_id)]
                                product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
                                product_categ_6_data = requests.get(product_categ_6_store_url,
                                                                    headers=headers_source).json()
                                product_categ_7_domain = [('nhcl_id', '=', line.categ_7.nhcl_id)]
                                product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
                                product_categ_7_data = requests.get(product_categ_7_store_url,
                                                                    headers=headers_source).json()
                                product_descrip_1_domain = [('nhcl_id', '=', line.descrip_1.nhcl_id)]
                                product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
                                product_descrip_1_data = requests.get(product_descrip_1_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_2_domain = [('nhcl_id', '=', line.descrip_2.nhcl_id)]
                                product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
                                product_descrip_2_data = requests.get(product_descrip_2_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_3_domain = [('nhcl_id', '=', line.descrip_3.nhcl_id)]
                                product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
                                product_descrip_3_data = requests.get(product_descrip_3_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_4_domain = [('nhcl_id', '=', line.descrip_4.nhcl_id)]
                                product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
                                product_descrip_4_data = requests.get(product_descrip_4_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_5_domain = [('nhcl_id', '=', line.descrip_5.nhcl_id)]
                                product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
                                product_descrip_5_data = requests.get(product_descrip_5_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_6_domain = [('nhcl_id', '=', line.descrip_6.nhcl_id)]
                                product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
                                product_descrip_6_data = requests.get(product_descrip_6_store_url,
                                                                      headers=headers_source).json()

                                product_categ_1_ids = product_categ_1_data.get("data")
                                if product_categ_1_ids:
                                    product_categ_1_id = product_categ_1_ids[0]["id"]
                                # else:
                                #     ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                #                                                        'add', 'failure',
                                #                                                        f"{self.name, self.move_line_ids_without_package.categ_1.name}Category 1 Not found")
                                product_categ_2_ids = product_categ_2_data.get("data")
                                if product_categ_2_ids:
                                    product_categ_2_id = product_categ_2_ids[0]["id"]
                                product_categ_3_ids = product_categ_3_data.get("data")
                                if product_categ_3_ids:
                                    product_categ_3_id = product_categ_3_ids[0]["id"]
                                product_categ_4_ids = product_categ_4_data.get("data")
                                if product_categ_4_ids:
                                    product_categ_4_id = product_categ_4_ids[0]["id"]
                                product_categ_5_ids = product_categ_5_data.get("data")
                                if product_categ_5_ids:
                                    product_categ_5_id = product_categ_5_ids[0]["id"]
                                product_categ_6_ids = product_categ_6_data.get("data")
                                if product_categ_6_ids:
                                    product_categ_6_id = product_categ_6_ids[0]["id"]
                                product_categ_7_ids = product_categ_7_data.get("data")
                                if product_categ_7_ids:
                                    product_categ_7_id = product_categ_7_ids[0]["id"]
                                product_descrip_1_ids = product_descrip_1_data.get("data")
                                if product_descrip_1_ids:
                                    product_descrip_1_id = product_descrip_1_ids[0]["id"]
                                product_descrip_2_ids = product_descrip_2_data.get("data")
                                if product_descrip_2_ids:
                                    product_descrip_2_id = product_descrip_2_ids[0]["id"]
                                product_descrip_3_ids = product_descrip_3_data.get("data")
                                if product_descrip_3_ids:
                                    product_descrip_3_id = product_descrip_3_ids[0]["id"]
                                product_descrip_4_ids = product_descrip_4_data.get("data")
                                if product_descrip_4_ids:
                                    product_descrip_4_id = product_descrip_4_ids[0]["id"]
                                product_descrip_5_ids = product_descrip_5_data.get("data")
                                if product_descrip_5_ids:
                                    product_descrip_5_id = product_descrip_5_ids[0]["id"]
                                product_descrip_6_ids = product_descrip_6_data.get("data")
                                if product_descrip_6_ids:
                                    product_descrip_6_id = product_descrip_6_ids[0]["id"]
                                mr_price = 0.0
                                if line.mr_price:
                                    mr_price = line.mr_price
                                if line and line.lot_id:
                                    lot_name = line.lot_id.name
                                else:
                                    lot_name = None
                                print("grthytjyjyu",stock_picking.get("create_id"))
                                if line:
                                    move_line_vals = {
                                        "picking_id": stock_picking.get("create_id"),
                                        "product_id": product_id[0]['id'],
                                        "quantity": line.quantity,
                                        "location_id": location_id[0]['id'],
                                        "location_dest_id": dest_location[0]["id"],
                                        "lot_name": lot_name,
                                        'internal_ref_lot': line.internal_ref_lot,
                                        'rs_price': line.rs_price if line.rs_price else 0,
                                        'cost_price': line.cost_price if line.cost_price else 0,
                                        'type_product': line.type_product,
                                        'segment': line.segment,
                                        'categ_1': product_categ_1_id if line.categ_1 else False,
                                        'categ_2': product_categ_2_id if line.categ_2 else False,
                                        'categ_3': product_categ_3_id if line.categ_3 else False,
                                        'categ_4': product_categ_4_id if line.categ_4 else False,
                                        'categ_5': product_categ_5_id if line.categ_5 else False,
                                        'categ_6': product_categ_6_id if line.categ_6 else False,
                                        'categ_7': product_categ_7_id if line.categ_7 else False,
                                        'descrip_1': product_descrip_1_id if line.descrip_1 else False,
                                        'descrip_2': product_descrip_2_id if line.descrip_2 else False,
                                        'descrip_3': product_descrip_3_id if line.descrip_3 else False,
                                        'descrip_4': product_descrip_4_id if line.descrip_4 else False,
                                        'descrip_5': product_descrip_5_id if line.descrip_5 else False,
                                        'descrip_6': product_descrip_6_id if line.descrip_6 else False,
                                    }
                                    print("move lines",move_line_vals)
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
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order',
                                                                          order.id,order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Damage to Main Delivery Order', order.id,order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                # stock_picking.button_validate()
                                order.nhcl_replication_status = True
                                order.validate_orders(deliver_order='damage_main')


            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def validate_orders(self, deliver_order):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                if deliver_order == 'damage_main':
                    ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/damage_main_action"
                elif deliver_order == 'main_damage':
                    ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/main_damage_action"
                elif deliver_order == 'return_main':
                    ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/return_main_action"
                elif deliver_order == 'exchange':
                    ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/return_exchange_action"
                elif deliver_order == 'pos_order':
                    ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/call_action"

                ho_pick_data = requests.post(ho_pick_validate_url, json={}, headers=headers_source)
                ho_pick_data.raise_for_status()
                print("ho_pick_data",ho_pick_data)
                # Access the JSON content from the response
                ho_pick_vals = ho_pick_data.json()
            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def confirm_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                ho_pick_validate_url = f"http://{ho_ip}:{ho_port}/api/sale.order/call_action"
                ho_pick_data = requests.post(ho_pick_validate_url, json={}, headers=headers_source)
                ho_pick_data.raise_for_status()
                print("ho_pick_data",ho_pick_data)
                # Access the JSON content from the response
                ho_pick_vals = ho_pick_data.json()
            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def get_return_main_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        product_categ_1_id = False
        product_categ_2_id = False
        product_categ_3_id = False
        product_categ_4_id = False
        product_categ_5_id = False
        product_categ_6_id = False

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "return_main")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False), ('stock_picking_type', '=', 'return_main'),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_pos_delivery_orders:
                    for order in self:
                        if order.stock_picking_type == "return_main":
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            picking_type_domain = [('stock_picking_type', '=', "return_main"),
                                                   ('company_id', '=', company_id[0]['id'])]
                            picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                            picking_type_data = requests.get(picking_type_url,
                                                             headers=headers_source).json()
                            picking_type = picking_type_data.get("data")
                            ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            location_domain = [('complete_name', '=', order.location_id.complete_name), ("active", "!=", False),
                                               ('usage', '=', 'internal'), ('company_id', '=', company_id[0]['id'])]
                            location_url = f"{ho_location_url}?domain={location_domain}&fields=['name','id']"
                            location_data = requests.get(location_url,
                                                         headers=headers_source).json()
                            location_id = location_data.get("data")
                            print('source', location_id)
                            store_location_dest_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            dest_location_domain = [('complete_name', '=', order.location_dest_id.complete_name),
                                                    ("active", "!=", False),
                                                    ('usage', '=', 'internal'),
                                                    ]
                            dest_location_url = f"{store_location_dest_url}?domain={dest_location_domain}&fields=['name','id']"
                            dest_location_data = requests.get(dest_location_url,
                                                              headers=headers_source).json()
                            dest_location = dest_location_data.get("data")
                            stock_picking_data = {
                                'picking_type_id': picking_type[0]['id'],
                                'origin': order.name,
                                'stock_type': order.stock_type,
                                'stock_picking_type': order.stock_picking_type,
                                'location_id': location_id[0]['id'] if location_id else False,
                                'location_dest_id': dest_location[0]['id'] if dest_location else False,
                                # 'company_id': location_id[0]['company_id'][0]['id'] if company_id else False,
                                'company_id': company_id[0]['id'] if company_id else False,
                                'move_type': 'direct',
                                'state': 'done',
                                'nhcl_store_delivery': True
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
                                product_attribute_value_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                                product_aging_line_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                                product_categ_1_domain = [('nhcl_id', '=', line.categ_1.nhcl_id)]
                                product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
                                product_categ_1_data = requests.get(product_categ_1_store_url,
                                                                    headers=headers_source).json()
                                product_categ_2_domain = [('nhcl_id', '=', line.categ_2.nhcl_id)]
                                product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
                                product_categ_2_data = requests.get(product_categ_2_store_url,
                                                                    headers=headers_source).json()
                                product_categ_3_domain = [('nhcl_id', '=', line.categ_3.nhcl_id)]
                                product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
                                product_categ_3_data = requests.get(product_categ_3_store_url,
                                                                    headers=headers_source).json()
                                product_categ_4_domain = [('nhcl_id', '=', line.categ_4.nhcl_id)]
                                product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
                                product_categ_4_data = requests.get(product_categ_4_store_url,
                                                                    headers=headers_source).json()
                                product_categ_5_domain = [('nhcl_id', '=', line.categ_5.nhcl_id)]
                                product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
                                product_categ_5_data = requests.get(product_categ_5_store_url,
                                                                    headers=headers_source).json()
                                product_categ_6_domain = [('nhcl_id', '=', line.categ_6.nhcl_id)]
                                product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
                                product_categ_6_data = requests.get(product_categ_6_store_url,
                                                                    headers=headers_source).json()
                                product_categ_7_domain = [('nhcl_id', '=', line.categ_7.nhcl_id)]
                                product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
                                product_categ_7_data = requests.get(product_categ_7_store_url,
                                                                    headers=headers_source).json()
                                product_descrip_1_domain = [('nhcl_id', '=', line.descrip_1.nhcl_id)]
                                product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
                                product_descrip_1_data = requests.get(product_descrip_1_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_2_domain = [('nhcl_id', '=', line.descrip_2.nhcl_id)]
                                product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
                                product_descrip_2_data = requests.get(product_descrip_2_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_3_domain = [('nhcl_id', '=', line.descrip_3.nhcl_id)]
                                product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
                                product_descrip_3_data = requests.get(product_descrip_3_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_4_domain = [('nhcl_id', '=', line.descrip_4.nhcl_id)]
                                product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
                                product_descrip_4_data = requests.get(product_descrip_4_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_5_domain = [('nhcl_id', '=', line.descrip_5.nhcl_id)]
                                product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
                                product_descrip_5_data = requests.get(product_descrip_5_store_url,
                                                                      headers=headers_source).json()
                                product_descrip_6_domain = [('nhcl_id', '=', line.descrip_6.nhcl_id)]
                                product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
                                product_descrip_6_data = requests.get(product_descrip_6_store_url,
                                                                      headers=headers_source).json()

                                product_categ_1_ids = product_categ_1_data.get("data")
                                if product_categ_1_ids:
                                    product_categ_1_id = product_categ_1_ids[0]["id"]
                                # else:
                                #     ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                #                                                        'add', 'failure',
                                #                                                        f"{self.name, self.move_line_ids_without_package.categ_1.name}Category 1 Not found")
                                product_categ_2_ids = product_categ_2_data.get("data")
                                if product_categ_2_ids:
                                    product_categ_2_id = product_categ_2_ids[0]["id"]
                                product_categ_3_ids = product_categ_3_data.get("data")
                                if product_categ_3_ids:
                                    product_categ_3_id = product_categ_3_ids[0]["id"]
                                product_categ_4_ids = product_categ_4_data.get("data")
                                if product_categ_4_ids:
                                    product_categ_4_id = product_categ_4_ids[0]["id"]
                                product_categ_5_ids = product_categ_5_data.get("data")
                                if product_categ_5_ids:
                                    product_categ_5_id = product_categ_5_ids[0]["id"]
                                product_categ_6_ids = product_categ_6_data.get("data")
                                if product_categ_6_ids:
                                    product_categ_6_id = product_categ_6_ids[0]["id"]
                                product_categ_7_ids = product_categ_7_data.get("data")
                                if product_categ_7_ids:
                                    product_categ_7_id = product_categ_7_ids[0]["id"]
                                product_descrip_1_ids = product_descrip_1_data.get("data")
                                if product_descrip_1_ids:
                                    product_descrip_1_id = product_descrip_1_ids[0]["id"]
                                product_descrip_2_ids = product_descrip_2_data.get("data")
                                if product_descrip_2_ids:
                                    product_descrip_2_id = product_descrip_2_ids[0]["id"]
                                product_descrip_3_ids = product_descrip_3_data.get("data")
                                if product_descrip_3_ids:
                                    product_descrip_3_id = product_descrip_3_ids[0]["id"]
                                product_descrip_4_ids = product_descrip_4_data.get("data")
                                if product_descrip_4_ids:
                                    product_descrip_4_id = product_descrip_4_ids[0]["id"]
                                product_descrip_5_ids = product_descrip_5_data.get("data")
                                if product_descrip_5_ids:
                                    product_descrip_5_id = product_descrip_5_ids[0]["id"]
                                product_descrip_6_ids = product_descrip_6_data.get("data")
                                if product_descrip_6_ids:
                                    product_descrip_6_id = product_descrip_6_ids[0]["id"]
                                mr_price = 0.0
                                if line.mr_price:
                                    mr_price = line.mr_price
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
                                        'internal_ref_lot': line.internal_ref_lot,
                                        'rs_price': line.rs_price if line.rs_price else 0,
                                        'cost_price': line.cost_price if line.cost_price else 0,
                                        'type_product': line.type_product,
                                        'segment': line.segment,
                                        'categ_1': product_categ_1_id if line.categ_1 else False,
                                        'categ_2': product_categ_2_id if line.categ_2 else False,
                                        'categ_3': product_categ_3_id if line.categ_3 else False,
                                        'categ_4': product_categ_4_id if line.categ_4 else False,
                                        'categ_5': product_categ_5_id if line.categ_5 else False,
                                        'categ_6': product_categ_6_id if line.categ_6 else False,
                                        'categ_7': product_categ_7_id if line.categ_7 else False,
                                        'descrip_1': product_descrip_1_id if line.descrip_1 else False,
                                        'descrip_2': product_descrip_2_id if line.descrip_2 else False,
                                        'descrip_3': product_descrip_3_id if line.descrip_3 else False,
                                        'descrip_4': product_descrip_4_id if line.descrip_4 else False,
                                        'descrip_5': product_descrip_5_id if line.descrip_5 else False,
                                        'descrip_6': product_descrip_6_id if line.descrip_6 else False,
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
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return to Main Delivery Order',
                                                                          order.id,order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return to Main Delivery Order', order.id,order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                order.nhcl_replication_status = True
                                order.validate_orders(deliver_order='return_main')




            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_customer_exchange_recipt_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetch the correct picking type for "Product Exchange - POS"
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "exchange")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False),
                     ('state', '=', 'done')])
                if store_pos_delivery_orders:
                    try:
                        for order in self:
                            if order.stock_picking_type == "exchange":
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
                                location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('complete_name','=', '{order.location_id.complete_name}'),('active','!=',False)]&fields=['name','id']"
                                location_data = requests.get(location_url, headers=headers_source).json()
                                location_id = location_data.get("data", [])

                                if not location_id:
                                    logging.warning(
                                        f"Location {order.location_id.name} not found in HO. Skipping order {order.name}.")
                                    continue  # Skip this order and move to the next one

                                location_id = location_id[0]['id']

                                # Fetch the destination location from HO
                                dest_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search?domain=[('cmr_location_type','=', '{order.location_dest_id.cmr_location_type}'),('active','!=',False)]&fields=['name','id']"
                                dest_location_data = requests.get(dest_location_url, headers=headers_source).json()
                                dest_location_id = dest_location_data.get("data", [])

                                if not dest_location_id:
                                    logging.warning(
                                        f"Destination Location {order.location_dest_id.complete_name} not found in HO. Skipping order {order.name}.")
                                    continue  # Skip this order and move to the next one

                                dest_location_id = dest_location_id[0]['id']

                                # Fetch or create the partner in HO
                                partner_url = f"http://{ho_ip}:{ho_port}/api/res.partner/search?domain=[('name','=', '{order.partner_id.name}'),('phone','=', '{order.partner_id.phone}')]"
                                partner_data = requests.get(partner_url, headers=headers_source).json()
                                partner = partner_data.get("data", [])
                                new_partner = False
                                if not partner:
                                    line_partner_category_data = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
                                    line_partner_category_data_domain = [('name', '=', 'Customer')]
                                    line_partner_category_data_url = f"{line_partner_category_data}?domain={line_partner_category_data_domain}"
                                    pos_partner_category = requests.get(line_partner_category_data_url,
                                                                        headers=headers_source).json()
                                    pos_partner_category_id = None
                                    if pos_partner_category and pos_partner_category.get("data"):
                                        pos_partner_category_id = pos_partner_category.get("data")[0]['id']
                                    partner_data = {
                                        'name': order.partner_id.name,
                                        'phone': order.partner_id.phone,
                                        'group_contact': pos_partner_category_id
                                    }
                                    partner_create_url = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                                    partner_create_response = requests.post(partner_create_url, headers=headers_source,
                                                                            json=[partner_data])
                                    partner_create_response.raise_for_status()
                                    new_partner = partner_create_response.json().get("create_id")

                                partner_id = partner[0]['id'] if partner else new_partner

                                # Fetch or create the Picking Type ID in HO
                                picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search?domain=[('name','=', '{order.picking_type_id.name}'),('company_id','=', {company_id})]"
                                picking_type_data = requests.get(picking_type_url, headers=headers_source).json()
                                picking_type = picking_type_data.get("data", [])
                                # Determine the stock picking data based on 'same store' or 'other store'
                                # Create stock move lines
                                stock_detail_lines = []
                                service = order.move_line_ids_without_package.filtered_domain([('product_id.nhcl_detailed_type', '=', 'service')])
                                for line in order.move_line_ids_without_package:
                                    if service:
                                        product_domain = [('name', '=', line.product_id.name)]
                                    else:
                                        product_domain = [('nhcl_id', '=', line.product_id.nhcl_id)]
                                    product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search?domain={product_domain}"
                                    product_data = requests.get(product_url, headers=headers_source).json()
                                    product_id = product_data.get("data", [])

                                    if not product_id:
                                        logging.warning(
                                            f"Product {line.product_id.name} not found in HO. Skipping move line for order {order.name}.")
                                        continue  # Skip this move line and move to the next

                                    product_id = product_id[0]['id']
                                    product_attribute_value_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                                    product_aging_line_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                                    product_categ_1_domain = [('nhcl_id', '=', line.categ_1.nhcl_id)]
                                    product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
                                    product_categ_1_data = requests.get(product_categ_1_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_2_domain = [('nhcl_id', '=', line.categ_2.nhcl_id)]
                                    product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
                                    product_categ_2_data = requests.get(product_categ_2_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_3_domain = [('nhcl_id', '=', line.categ_3.nhcl_id)]
                                    product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
                                    product_categ_3_data = requests.get(product_categ_3_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_4_domain = [('nhcl_id', '=', line.categ_4.nhcl_id)]
                                    product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
                                    product_categ_4_data = requests.get(product_categ_4_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_5_domain = [('nhcl_id', '=', line.categ_5.nhcl_id)]
                                    product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
                                    product_categ_5_data = requests.get(product_categ_5_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_6_domain = [('nhcl_id', '=', line.categ_6.nhcl_id)]
                                    product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
                                    product_categ_6_data = requests.get(product_categ_6_store_url,
                                                                        headers=headers_source).json()
                                    product_categ_7_domain = [('nhcl_id', '=', line.categ_7.nhcl_id)]
                                    product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
                                    product_categ_7_data = requests.get(product_categ_7_store_url,
                                                                        headers=headers_source).json()
                                    product_descrip_1_domain = [('nhcl_id', '=', line.descrip_1.nhcl_id)]
                                    product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
                                    product_descrip_1_data = requests.get(product_descrip_1_store_url,
                                                                          headers=headers_source).json()
                                    product_descrip_2_domain = [('nhcl_id', '=', line.descrip_2.nhcl_id)]
                                    product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
                                    product_descrip_2_data = requests.get(product_descrip_2_store_url,
                                                                          headers=headers_source).json()
                                    product_descrip_3_domain = [('nhcl_id', '=', line.descrip_3.nhcl_id)]
                                    product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
                                    product_descrip_3_data = requests.get(product_descrip_3_store_url,
                                                                          headers=headers_source).json()
                                    product_descrip_4_domain = [('nhcl_id', '=', line.descrip_4.nhcl_id)]
                                    product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
                                    product_descrip_4_data = requests.get(product_descrip_4_store_url,
                                                                          headers=headers_source).json()
                                    product_descrip_5_domain = [('nhcl_id', '=', line.descrip_5.nhcl_id)]
                                    product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
                                    product_descrip_5_data = requests.get(product_descrip_5_store_url,
                                                                          headers=headers_source).json()
                                    product_descrip_6_domain = [('nhcl_id', '=', line.descrip_6.nhcl_id)]
                                    product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
                                    product_descrip_6_data = requests.get(product_descrip_6_store_url,
                                                                          headers=headers_source).json()

                                    product_categ_1_ids = product_categ_1_data.get("data")
                                    if product_categ_1_ids:
                                        product_categ_1_id = product_categ_1_ids[0]["id"]
                                    # else:
                                    #     ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                    #                                                        'add', 'failure',
                                    #                                                        f"{self.name, self.move_line_ids_without_package.categ_1.name}Category 1 Not found")
                                    product_categ_2_ids = product_categ_2_data.get("data")
                                    if product_categ_2_ids:
                                        product_categ_2_id = product_categ_2_ids[0]["id"]
                                    product_categ_3_ids = product_categ_3_data.get("data")
                                    if product_categ_3_ids:
                                        product_categ_3_id = product_categ_3_ids[0]["id"]
                                    product_categ_4_ids = product_categ_4_data.get("data")
                                    if product_categ_4_ids:
                                        product_categ_4_id = product_categ_4_ids[0]["id"]
                                    product_categ_5_ids = product_categ_5_data.get("data")
                                    if product_categ_5_ids:
                                        product_categ_5_id = product_categ_5_ids[0]["id"]
                                    product_categ_6_ids = product_categ_6_data.get("data")
                                    if product_categ_6_ids:
                                        product_categ_6_id = product_categ_6_ids[0]["id"]
                                    product_categ_7_ids = product_categ_7_data.get("data")
                                    if product_categ_7_ids:
                                        product_categ_7_id = product_categ_7_ids[0]["id"]
                                    product_descrip_1_ids = product_descrip_1_data.get("data")
                                    if product_descrip_1_ids:
                                        product_descrip_1_id = product_descrip_1_ids[0]["id"]
                                    product_descrip_2_ids = product_descrip_2_data.get("data")
                                    if product_descrip_2_ids:
                                        product_descrip_2_id = product_descrip_2_ids[0]["id"]
                                    product_descrip_3_ids = product_descrip_3_data.get("data")
                                    if product_descrip_3_ids:
                                        product_descrip_3_id = product_descrip_3_ids[0]["id"]
                                    product_descrip_4_ids = product_descrip_4_data.get("data")
                                    if product_descrip_4_ids:
                                        product_descrip_4_id = product_descrip_4_ids[0]["id"]
                                    product_descrip_5_ids = product_descrip_5_data.get("data")
                                    if product_descrip_5_ids:
                                        product_descrip_5_id = product_descrip_5_ids[0]["id"]
                                    product_descrip_6_ids = product_descrip_6_data.get("data")
                                    if product_descrip_6_ids:
                                        product_descrip_6_id = product_descrip_6_ids[0]["id"]
                                    mr_price = 0.0
                                    if line.mr_price:
                                        mr_price = line.mr_price
                                    cost_price = line.cost_price
                                    print("cost_price", cost_price)
                                    move_line_vals = {
                                        "product_id": product_id,
                                        "cost_price": cost_price,
                                        "quantity": line.quantity,
                                        "location_id": location_id,
                                        "location_dest_id": dest_location_id,
                                        "lot_name": line.lot_id.name if line.lot_id else None,
                                        'internal_ref_lot': line.internal_ref_lot,
                                        'rs_price': line.rs_price if line.rs_price else 0,
                                        'type_product': line.type_product,
                                        'segment': line.segment,
                                        'categ_1': product_categ_1_id if line.categ_1 else False,
                                        'categ_2': product_categ_2_id if line.categ_2 else False,
                                        'categ_3': product_categ_3_id if line.categ_3 else False,
                                        'categ_4': product_categ_4_id if line.categ_4 else False,
                                        'categ_5': product_categ_5_id if line.categ_5 else False,
                                        'categ_6': product_categ_6_id if line.categ_6 else False,
                                        'categ_7': product_categ_7_id if line.categ_7 else False,
                                        'descrip_1': product_descrip_1_id if line.descrip_1 else False,
                                        'descrip_2': product_descrip_2_id if line.descrip_2 else False,
                                        'descrip_3': product_descrip_3_id if line.descrip_3 else False,
                                        'descrip_4': product_descrip_4_id if line.descrip_4 else False,
                                        'descrip_5': product_descrip_5_id if line.descrip_5 else False,
                                        'descrip_6': product_descrip_6_id if line.descrip_6 else False,
                                    }
                                    stock_detail_lines.append((0, 0, move_line_vals))
                                    print("move_line_vals", move_line_vals)
                                if order.company_type == 'same':
                                    print("ytfiygiyiyvyiv", partner_id,dest_location_id,location_id,stock_detail_lines)
                                    stock_picking_data = {
                                        'partner_id': partner_id,
                                        'picking_type_id': picking_type[0]["id"],
                                        'origin': order.name,
                                        'return_counter': "RF Counter",
                                        'location_id': location_id,
                                        'location_dest_id': dest_location_id,
                                        'company_id': company_id,
                                        'stock_type': 'pos_exchange',
                                        'company_type': order.company_type,
                                        'nhcl_store_delivery': True,
                                        'move_line_ids_without_package': stock_detail_lines,

                                    }
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
                                        'return_counter': "RF Counter",
                                        'location_id': location_id,
                                        'location_dest_id': dest_location_id,
                                        'company_id': company_id,
                                        'store_name': 2,
                                        'stock_type': 'pos_exchange',
                                        'company_type': order.company_type,
                                        'store_pos_order': order.store_pos_order,
                                        'nhcl_store_delivery': True,
                                        'move_line_ids_without_package': stock_detail_lines,

                                    }

                                # Create stock picking in HO
                                stock_picking_create_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/create"
                                stock_picking_create_response = requests.post(stock_picking_create_url,
                                                                              headers=headers_source,
                                                                              json=[stock_picking_data])
                                stock_picking_create_response.raise_for_status()
                                stock_picking = stock_picking_create_response.json()
                                if stock_picking:
                                    message = stock_picking.get("message", "No message provided")
                                    if stock_picking['success'] == True:
                                        order.nhcl_replication_status = True
                                        # order.validate_orders(deliver_order = 'exchange')
                                        _logger.info(
                                            f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Journal Entry {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        ho_id.create_cmr_transaction_server_replication_log('success',
                                                                                            'Server Connected Successfully')
                                        ho_id.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order',
                                                                                     order.id,order.name,
                                                                                     200,
                                                                                     'add', 'success',
                                                                                     f"Successfully created Journal Entry {order.name}")

                                    else:
                                        _logger.info(
                                            f"Failed to create Journal Entry {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Journal Entry  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                        ho_id.create_cmr_transaction_server_replication_log('success', message)
                                        ho_id.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order',
                                                                                     order.id,order.name,
                                                                                     200,
                                                                                     'add', 'failure', message)

                            else:
                                logging.warning(f"Skipping order {order.name}, location not 'Customers'.")
                    except Exception as e:
                        logging.error(f"Error while processing order {order.name}: {e}")
                        ho.create_cmr_transaction_server_replication_log("failure", str(e))
                        ho.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order', order.id,order.name, 500, 'add', 'failure', str(e))

            except Exception as e:
                logging.error(f"Error while processing order {order.name}: {e}")
                ho.create_cmr_transaction_server_replication_log("failure", str(e))
                ho.create_cmr_transaction_replication_log('POS Customer Exchange Receipt Order', order.id,order.name, 500, 'add', 'failure', str(e))


    def get_regular_delivery_orders(self):
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
                            detail_sale_order = []
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            for line in order.move_line_ids_without_package:
                                product = line.product_id
                                product_domain = [('nhcl_id', '=', product.nhcl_id)]
                                ho_product_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                                product_url = f"{ho_product_url}?domain={product_domain}"
                                product_data = requests.get(product_url,
                                                            headers=headers_source).json()
                                product_id = product_data.get("data")
                                if line and line.lot_id:
                                    ho_lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                    stock_lot_domain = [('name', '=', line.lot_id.name), ('company_id', '=', company_id[0]['id'])]
                                    stock_lot_url = f"{ho_lot_url}?domain={stock_lot_domain}"
                                    stock_lot_data = requests.get(stock_lot_url,
                                                                headers=headers_source).json()
                                    stock_lot_id = stock_lot_data.get("data")
                                    if stock_lot_id:
                                        lot = stock_lot_id[0]['id']
                                    else:
                                        ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,order.name, 200,
                                                                                           'add', 'failure',
                                                                                           f"{order.name, line.lot_id.name}Lot Not found")
                                if line and lot:
                                    sale_order_line_vals = {
                                        "product_id": product_id[0]['id'],
                                        "product_uom_qty": line.quantity,
                                        "price_unit": line.cost_price,
                                        "branded_barcode": line.internal_ref_lot,
                                        'lot_ids': [(4, lot)],
                                    }
                                    detail_sale_order.append((0,0,sale_order_line_vals))

                            if detail_sale_order:
                                sale_order = {
                                    'partner_id': 1,
                                    'origin': order.name,
                                    'so_type': order.stock_type,
                                    'nhcl_sale_type': 'regular',
                                    'stock_type': order.stock_picking_type,
                                    'company_id': company_id[0]['id'],
                                    'nhcl_store_delivery': True,
                                    'order_line' : detail_sale_order,

                                }
                                sale_order_create = f"http://{ho_ip}:{ho_port}/api/sale.order/create"
                                sale_order_create_data = requests.post(sale_order_create,
                                                                   headers=headers_source, json=[sale_order])
                                sale_order_create_data.raise_for_status()
                                sale_order = sale_order_create_data.json()
                                message = sale_order.get("message", "No message provided")
                                if sale_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Regular Delivery Order',
                                                                              order.id,order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Regular Delivery Order', order.id,order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                                    order.confirm_orders()

            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

    def get_damage_delivery_orders(self):
        ho_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        for ho in ho_id:
            try:
                ho_ip = ho.nhcl_terminal_ip
                ho_port = ho.nhcl_port_no
                store_api_key = ho.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                picking_type_id = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage")])
                store_pos_delivery_orders = self.env['stock.picking'].search(
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False), ('stock_picking_type', '=', 'damage'),
                     ('state', '=', 'done')])
                # Fetching delivery orders
                if store_pos_delivery_orders:
                    for order in self:
                        if order.stock_picking_type == "damage":
                            company_search = f"http://{ho_ip}:{ho_port}/api/res.company/search"
                            company_domain = [('name', '=', order.company_id.name)]
                            company_url = f"{company_search}?domain={company_domain}"
                            company_data = requests.get(company_url, headers=headers_source).json()
                            company_id = company_data.get("data")
                            # ho_stock_picking_type_url = f"http://{ho_ip}:{ho_port}/api/stock.picking.type/search"
                            # picking_type_domain = [('stock_picking_type', '=', "damage"),
                            #                        ('company_id', '=', company_id[0]['id'])]
                            # picking_type_url = f"{ho_stock_picking_type_url}?domain={picking_type_domain}"
                            # picking_type_data = requests.get(picking_type_url,
                            #                                  headers=headers_source).json()
                            # picking_type = picking_type_data.get("data")
                            # ho_location_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            # location_domain = [('complete_name', '=', order.location_id.complete_name), ("active", "!=", False),
                            #                    ('usage', '=', 'internal'), ('company_id', '=', company_id[0]['id'])]
                            # location_url = f"{ho_location_url}?domain={location_domain}"
                            # location_data = requests.get(location_url,
                            #                              headers=headers_source).json()
                            # location_id = location_data.get("data")
                            # print('source', location_id)
                            # store_location_dest_url = f"http://{ho_ip}:{ho_port}/api/stock.location/search"
                            # dest_location_domain = [('complete_name', '=', order.location_dest_id.complete_name),
                            #                         ("active", "!=", False),
                            #                         ('usage', '=', 'internal'),
                            #                         ]
                            # dest_location_url = f"{store_location_dest_url}?domain={dest_location_domain}"
                            # dest_location_data = requests.get(dest_location_url,
                            #                                   headers=headers_source).json()
                            # dest_location = dest_location_data.get("data")
                            sale_order = {
                                'partner_id': 1,
                                'origin': order.name,
                                'so_type': order.stock_type,
                                'nhcl_sale_type': 'regular',
                                'stock_type': order.stock_picking_type,
                                'company_id': company_id[0]['id'],
                                'nhcl_store_delivery': True

                            }
                            sale_order_create = f"http://{ho_ip}:{ho_port}/api/sale.order/create"
                            sale_order_create_data = requests.post(sale_order_create,
                                                               headers=headers_source, json=[sale_order])
                            sale_order_create_data.raise_for_status()
                            # Access the JSON content from the response
                            sale_order = sale_order_create_data.json()
                            print(sale_order)
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
                                    ho_lot_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                    stock_lot_domain = [('name', '=', line.lot_id.name), ('company_id', '=', company_id[0]['id'])]
                                    stock_lot_url = f"{ho_lot_url}?domain={stock_lot_domain}"
                                    stock_lot_data = requests.get(stock_lot_url,
                                                                headers=headers_source).json()
                                    stock_lot_id = stock_lot_data.get("data")
                                    lot = stock_lot_id[0]['id']
                                else:
                                    lot = False
                                print(sale_order.get("create_id"))
                                if line:
                                    sale_order_line_vals = {
                                        "order_id": sale_order.get("create_id"),
                                        "product_id": product_id[0]['id'],
                                        "product_uom_qty": line.quantity,
                                        "price_unit": line.cost_price,
                                        'lot_ids': [(4, lot)],
                                    }

                                    print(sale_order_line_vals)
                                    sale_order_line_create = f"http://{ho_ip}:{ho_port}/api/sale.order.line/create"
                                    sale_order_line_data = requests.post(sale_order_line_create,
                                                                         headers=headers_source,
                                                                         json=[sale_order_line_vals])
                                    sale_order_line_data.raise_for_status()
                                    # Access the JSON content from the response
                                    sale_order_line = sale_order_line_data.json()
                                    sale_line = sale_order_line.get("data")
                            print('sale_order', sale_order)
                            message = sale_order.get("message", "No message provided")
                            if sale_order.get("success") == False:
                                _logger.info(
                                    f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Damage Delivery Order',
                                                                          order.id,order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Damage Delivery Order', order.id,order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                # stock_picking.button_validate()
                                order.nhcl_replication_status = True
                                order.confirm_orders()


            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)

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
                    [('picking_type_id', '=', picking_type_id.id), ('nhcl_replication_status', '=', False), ('stock_picking_type', '=', 'return'),
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
                                print("********",barcode_lines)
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
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return Delivery Order',
                                                                          order.id,order.name,
                                                                          200,
                                                                          'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                ho.create_cmr_transaction_server_replication_log('success', message)
                                ho.create_cmr_transaction_replication_log('Return Delivery Order', order.id,order.name,
                                                                          200,
                                                                          'add', 'success',
                                                                          f"Successfully created Delivery Order {order.name}")
                                order.nhcl_replication_status = True


            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)


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
            res = super().action_done()
            return res

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.nhcl_replication_status == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_regular_batch_delivery_orders(self):
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
                            batch = []
                            ho_master_search = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search"
                            ho_master_domain = [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True)]
                            ho_master_url = f"{ho_master_search}?domain={ho_master_domain}"
                            ho_master_data = requests.get(ho_master_url, headers=headers_source).json()
                            ho_master_id = ho_master_data.get("data")[0]
                            for picking in order.picking_ids:
                                picking.get_regular_delivery_orders()
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
                                    if ho_transporter_data.get("data"):
                                        ho_transporter = ho_transporter_data.get("data")[0]
                                        ho_transporter_id = ho_transporter.get('id')
                                if picking.transpoter_route_id:
                                    ho_transporter_route_search_url = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/search"
                                    ho_transporter_route_domain = [('nhcl_id', '=', picking.transpoter_route_id.nhcl_id)]
                                    ho_transporter_route_url = f"{ho_transporter_route_search_url}?domain={ho_transporter_route_domain}"
                                    ho_transporter_route_data = requests.get(ho_transporter_route_url,
                                                                       headers=headers_source).json()
                                    if ho_transporter_route_data.get("data"):
                                        ho_transporter_route = ho_transporter_route_data.get("data")[0]
                                        ho_transporter_route_id = ho_transporter_route.get('id')
                                barcode_lines = []
                                for rec in picking.stock_picking_delivery_ids:
                                    barcode_lines.append((0, 0, {
                                        'serial_no': rec.serial_no,
                                        'barcode': rec.barcode,
                                        'sequence': rec.sequence,
                                    }))
                                    # print("********", barcode_lines)
                                transport_data = {
                                    'stock_picking_type': picking.stock_picking_type,
                                    'lr_number': picking.lr_number if picking.lr_number else None,
                                    'vehicle_number': picking.vehicle_number if picking.vehicle_number else None,
                                    'driver_name': picking.driver_name if picking.driver_name else None,
                                    'no_of_parcel': picking.no_of_parcel if picking.no_of_parcel else None,
                                    'nhcl_tracking_number': picking.tracking_number,
                                    'transpoter_id': ho_transporter_id,
                                    'transpoter_route_id': ho_transporter_route_id,
                                    'stock_picking_delivery_ids': barcode_lines,
                                }
                                try:
                                    ho_delivery_transporter_data_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/{transporter_update_id}"
                                    ho_delivery_transporter_data = requests.put(ho_delivery_transporter_data_url,
                                                                                  headers=headers_source,
                                                                                  json=transport_data)
                                    ho_delivery_transporter_data.raise_for_status()
                                    ho_delivery_transporter = ho_delivery_transporter_data.json()

                                except Exception as e:
                                    ho.create_cmr_transaction_server_replication_log("failure", e)
                            store_batch_data = {
                                'name': order.name,
                                "user_id": 2,
                                "nhcl_company": ho_master_id.get('id') if ho_master_id else False,
                                'picking_ids': batch,
                                'company_id': company_id.get('id'),

                            }
                            print("store_batch_data",store_batch_data)
                            try:
                                store_batch_order_create = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                                store_batch_order_create_data = requests.post(store_batch_order_create,
                                                                       headers=headers_source, json=[store_batch_data])
                                store_batch_order_create_data.raise_for_status()
                                store_batch_order = store_batch_order_create_data.json()
                                message = store_batch_order.get("message", "No message provided")
                                if store_batch_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Regular Batch Delivery Order',
                                                                              order.id,order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Regular Batch Delivery Order', order.id,order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                            except Exception as e:
                                ho.create_cmr_transaction_server_replication_log("failure", e)
                        except Exception as e:
                            ho.create_cmr_transaction_server_replication_log("failure", e)
            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)


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
                                    ho_transporter_route_domain = [('nhcl_id', '=', picking.transpoter_route_id.nhcl_id)]
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
                                print("transport_data",transport_data)
                                try:
                                    ho_delivery_transporter_data_url = f"http://{ho_ip}:{ho_port}/api/stock.picking/{transporter_update_id}"
                                    ho_delivery_transporter_data = requests.put(ho_delivery_transporter_data_url,
                                                                                  headers=headers_source,
                                                                                  json=transport_data)
                                    ho_delivery_transporter_data.raise_for_status()
                                    ho_delivery_transporter = ho_delivery_transporter_data.json()

                                except Exception as e:
                                    ho.create_cmr_transaction_server_replication_log("failure", e)
                            store_batch_data = {
                                'name': order.name,
                                "user_id": 2,
                                "nhcl_company":ho_master_id.get('id') if ho_master_id else False,
                                'picking_ids': batch,
                                'company_id': company_id.get('id'),

                            }
                            print("store_batch_data",store_batch_data)
                            try:
                                store_batch_order_create = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                                store_batch_order_create_data = requests.post(store_batch_order_create,
                                                                       headers=headers_source, json=[store_batch_data])
                                store_batch_order_create_data.raise_for_status()
                                store_batch_order = store_batch_order_create_data.json()
                                message = store_batch_order.get("message", "No message provided")
                                if store_batch_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Damage Batch Delivery Order',
                                                                              order.id,order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Damage Batch Delivery Order', order.id,order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                            except Exception as e:
                                ho.create_cmr_transaction_server_replication_log("failure", e)
                        except Exception as e:
                            ho.create_cmr_transaction_server_replication_log("failure", e)
            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)


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
                                "nhcl_company":ho_master_id.get('id') if ho_master_id else False,
                                'picking_ids': batch,
                                'company_id': company_id.get('id'),

                            }
                            print("store_batch_data",store_batch_data)
                            try:
                                store_batch_order_create = f"http://{ho_ip}:{ho_port}/api/stock.picking.batch/create"
                                store_batch_order_create_data = requests.post(store_batch_order_create,
                                                                       headers=headers_source, json=[store_batch_data])
                                store_batch_order_create_data.raise_for_status()
                                store_batch_order = store_batch_order_create_data.json()
                                message = store_batch_order.get("message", "No message provided")
                                if store_batch_order.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Delivery Order {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Return Batch Delivery Order',
                                                                              order.id,order.name,
                                                                              200,
                                                                              'add', 'failure', message)
                                else:
                                    _logger.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Delivery Order {order.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    ho.create_cmr_transaction_server_replication_log('success', message)
                                    ho.create_cmr_transaction_replication_log('Return Batch Delivery Order', order.id,order.name,
                                                                              200,
                                                                              'add', 'success',
                                                                              f"Successfully created Delivery Order {order.name}")
                                    order.nhcl_replication_status = True
                            except Exception as e:
                                ho.create_cmr_transaction_server_replication_log("failure", e)
                        except Exception as e:
                            ho.create_cmr_transaction_server_replication_log("failure", e)
            except Exception as e:
                ho.create_cmr_transaction_server_replication_log("failure", e)
