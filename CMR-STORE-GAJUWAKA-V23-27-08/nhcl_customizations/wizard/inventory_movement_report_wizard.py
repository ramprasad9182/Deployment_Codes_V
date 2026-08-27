from odoo import models, fields
from odoo.exceptions import ValidationError
from datetime import datetime, time, date


class InventoryMovementReportWizard(models.TransientModel):
    _name = "inventory.movement.report.wizard"
    _description = "inventory movement report wizard"

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")


    def action_generate(self):

        today = date.today()

        if not self.from_date:
            self.from_date = today

        if not self.to_date:
            self.to_date = today

        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValidationError("From Date cannot be greater than To Date.")

        self.env['inventory.movement.report'].search([]).unlink()

        # Base domain
        base_domain = [
            ('state', '=', 'done'),
            ('product_id.detailed_type', '=', 'product'),
        ]

        if self.from_date:
            from_dt = datetime.combine(self.from_date, time.min)
            base_domain.append(('picking_id.date_done', '>=', from_dt))

        if self.to_date:
            to_dt = datetime.combine(self.to_date, time.max)
            base_domain.append(('picking_id.date_done', '<=', to_dt))

        # All picking types
        picking_types = [
            'receipt',
            'return',
            'main_damage',
            'damage',
            'damage_main',
            'pos_order',
            'exchange',
            'return_main',
        ]

        product_data = {}
        opening_qty_dict = {}
        opening_val_dict = {}

        if self.from_date:
            from_dt = datetime.combine(self.from_date, time.min)

            for ptype in ['receipt', 'return', 'return_main', 'damage', 'pos_order', 'main_damage', 'damage_main']:
            # for ptype in ['receipt', 'return', 'return_main', 'damage', 'pos_order', 'exchange']:

                domain = [
                    ('state', '=', 'done'),
                    ('product_id.detailed_type', '=', 'product'),
                    ('picking_id.stock_picking_type', '=', ptype),
                    ('picking_id.date_done', '<', from_dt)
                ]

                qty_data = self.env['stock.move'].read_group(
                    domain,
                    ['quantity:sum'],
                    ['product_id'],
                    lazy=False
                )

                val_domain = [
                    ('move_id.state', '=', 'done'),
                    ('move_id.product_id.detailed_type', '=', 'product'),
                    ('move_id.picking_id.stock_picking_type', '=', ptype),
                    ('move_id.picking_id.date_done', '<', from_dt)
                ]

                val_data = self.env['stock.move.line'].read_group(
                    val_domain,
                    ['rs_price:sum'],
                    ['product_id'],
                    lazy=False
                )

                val_dict = {
                    v['product_id'][0]: v['rs_price']
                    for v in val_data if v.get('product_id')
                }

                for q in qty_data:
                    product_id = q['product_id'][0]
                    qty = q['quantity']
                    val = val_dict.get(product_id, 0.0)

                    if product_id not in opening_qty_dict:
                        opening_qty_dict[product_id] = 0.0
                        opening_val_dict[product_id] = 0.0

                    if ptype in ['receipt', 'return_main','damage_main']:
                    # if ptype in ['receipt', 'return_main', 'exchange']:
                        opening_qty_dict[product_id] += qty
                        opening_val_dict[product_id] += val

                    elif ptype in ['return', 'damage', 'pos_order','main_damage']:
                    # elif ptype in ['return', 'damage', 'pos_order']:
                        opening_qty_dict[product_id] -= qty
                        opening_val_dict[product_id] -= val

        for ptype in picking_types:

            domain = base_domain + [
                ('picking_id.stock_picking_type', '=', ptype)
            ]

            qty_data = self.env['stock.move'].read_group(
                domain,
                ['quantity:sum'],
                ['product_id'],
                lazy=False
            )

            rsp_domain = [
                ('move_id.state', '=', 'done'),
                ('move_id.product_id.detailed_type', '=', 'product'),
                ('move_id.picking_id.stock_picking_type', '=', ptype),
            ]

            if self.from_date:
                rsp_domain.append(('move_id.picking_id.date_done', '>=', from_dt))

            if self.to_date:
                rsp_domain.append(('move_id.picking_id.date_done', '<=', to_dt))

            rsp_data = self.env['stock.move.line'].read_group(
                rsp_domain,
                ['rs_price:sum'],
                ['product_id'],
                lazy=False
            )

            # Convert rsp to dict
            rsp_dict = {
                data['product_id'][0]: data['rs_price']
                for data in rsp_data if data.get('product_id')
            }

            for data in qty_data:

                product_id = data['product_id'][0]
                qty = data['quantity']
                rs_total = rsp_dict.get(product_id, 0.0)

                if product_id not in product_data:
                    product_data[product_id] = {
                        'receipt_qty': 0.0, 'receipt_rs_total': 0.0,
                        'delivery_qty': 0.0, 'delivery_rs_total': 0.0,
                        'maintodamage_qty': 0.0, 'maintodamage_rs_total': 0.0,
                        'goodsreturn_damage_qty': 0.0, 'goodsreturn_damage_rs_total': 0.0,
                        'damagetomain_qty': 0.0, 'damagetomain_rs_total': 0.0,
                        'pos_order_qty': 0.0, 'pos_order_rs_total': 0.0,
                        # 'pos_exchange_qty': 0.0, 'pos_exchange_rs_total': 0.0,
                        'pos_return_qty': 0.0, 'pos_return_rs_total': 0.0,
                    }

                if ptype == 'receipt':
                    product_data[product_id]['receipt_qty'] = qty
                    product_data[product_id]['receipt_rs_total'] = rs_total

                elif ptype == 'return':
                    product_data[product_id]['delivery_qty'] = qty
                    product_data[product_id]['delivery_rs_total'] = rs_total

                elif ptype == 'main_damage':
                    product_data[product_id]['maintodamage_qty'] = qty
                    product_data[product_id]['maintodamage_rs_total'] = rs_total

                elif ptype == 'damage':
                    product_data[product_id]['goodsreturn_damage_qty'] = qty
                    product_data[product_id]['goodsreturn_damage_rs_total'] = rs_total

                elif ptype == 'damage_main':
                    product_data[product_id]['damagetomain_qty'] = qty
                    product_data[product_id]['damagetomain_rs_total'] = rs_total

                elif ptype == 'pos_order':
                    product_data[product_id]['pos_order_qty'] = qty
                    product_data[product_id]['pos_order_rs_total'] = rs_total

                # elif ptype == 'exchange':
                #     product_data[product_id]['pos_exchange_qty'] = qty
                #     product_data[product_id]['pos_exchange_rs_total'] = rs_total

                elif ptype == 'return_main':
                    product_data[product_id]['pos_return_qty'] = qty
                    product_data[product_id]['pos_return_rs_total'] = rs_total

        # Create records
        # for product_id, values in product_data.items():
        all_product_ids = set(product_data.keys()) | set(opening_qty_dict.keys())

        for product_id in all_product_ids:
            values = product_data.get(product_id, {
                'receipt_qty': 0.0, 'receipt_rs_total': 0.0,
                'delivery_qty': 0.0, 'delivery_rs_total': 0.0,
                'maintodamage_qty': 0.0, 'maintodamage_rs_total': 0.0,
                'goodsreturn_damage_qty': 0.0, 'goodsreturn_damage_rs_total': 0.0,
                'damagetomain_qty': 0.0, 'damagetomain_rs_total': 0.0,
                'pos_order_qty': 0.0, 'pos_order_rs_total': 0.0,
                # 'pos_exchange_qty': 0.0, 'pos_exchange_rs_total': 0.0,
                'pos_return_qty': 0.0, 'pos_return_rs_total': 0.0,
            })

            product = self.env['product.product'].browse(product_id)
            category = product.categ_id

            parts = category.display_name.split("/") if category else []

            division_name = parts[0].strip() if len(parts) >= 1 else False
            section_name = " / ".join(parts[:2]) if len(parts) >= 2 else False
            department_name = " / ".join(parts[:3]) if len(parts) >= 3 else False
            category_name = " / ".join(parts[:4]) if len(parts) >= 4 else False

            opening_qty = opening_qty_dict.get(product_id, 0.0)
            opening_val = opening_val_dict.get(product_id, 0.0)

            closing_qty = (
                    opening_qty
                    + values['receipt_qty']
                    # + values['pos_exchange_qty']
                    + values['pos_return_qty']
                    - values['delivery_qty']
                    - values['goodsreturn_damage_qty']
                    - values['pos_order_qty']
                + values['damagetomain_qty']
                - values['maintodamage_qty']
            )

            closing_val = (
                    opening_val
                    + values['receipt_rs_total']
                    # + values['pos_exchange_rs_total']
                    + values['pos_return_rs_total']
                    - values['delivery_rs_total']
                    - values['goodsreturn_damage_rs_total']
                    - values['pos_order_rs_total']
                + values['damagetomain_rs_total']
                - values['maintodamage_rs_total']
            )

            self.env['inventory.movement.report'].create({
                'product_id': product_id,
                'from_date': self.from_date,
                'to_date': self.to_date,

                'receipt_qty': values['receipt_qty'],
                'receipt_rs_total': values['receipt_rs_total'],

                'delivery_qty': values['delivery_qty'],
                'delivery_rs_total': values['delivery_rs_total'],

                'maintodamage_qty': values['maintodamage_qty'],
                'maintodamage_rs_total': values['maintodamage_rs_total'],

                'goodsreturn_damage_qty': values['goodsreturn_damage_qty'],
                'goodsreturn_damage_rs_total': values['goodsreturn_damage_rs_total'],

                'damagetomain_qty': values['damagetomain_qty'],
                'damagetomain_rs_total': values['damagetomain_rs_total'],

                'pos_order_qty': values['pos_order_qty'],
                'pos_order_rs_total': values['pos_order_rs_total'],

                # 'pos_exchange_qty': values['pos_exchange_qty'],
                # 'pos_exchange_rs_total': values['pos_exchange_rs_total'],

                'pos_return_qty': values['pos_return_qty'],
                'pos_return_rs_total': values['pos_return_rs_total'],

                'division_name': division_name,
                'section_name': section_name,
                'department_name': department_name,
                'category_name': category_name,

                'opening_qty': opening_qty,
                'opening_rs_total': opening_val,
                'closing_qty': closing_qty,
                'closing_rs_total': closing_val,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }