from odoo import models, fields


class NhclStockReport(models.Model):
    _name = 'nhcl.stock.report'
    _description = 'Stock Report'
    _auto = False

    site = fields.Char(string='Site')
    family = fields.Char(string='Family')
    section = fields.Char(string='Section')
    class_name = fields.Char(string='Class')
    brick = fields.Char(string='Brick')
    article = fields.Char(string='Article')
    ageing = fields.Char(string='Ageing')
    brand = fields.Char(string='Brand')
    design = fields.Char(string='Design')

    unit_rsp = fields.Float(string='Unit RSP')
    cp = fields.Float(string='CP')
    mrp = fields.Float(string='MRP')

    description_8 = fields.Char(string='Description 8')
    promo = fields.Char(string='Promo')
    on_hand_qty = fields.Float(string='On Hand Qty')
    barcode = fields.Char(string='Barcode')



    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS nhcl_stock_report CASCADE;

            CREATE OR REPLACE VIEW nhcl_stock_report AS (

                WITH category_map AS (
                    SELECT
                        pc.id,
                        pc.complete_name,

                        NULLIF(
                            split_part(
                                trim(trailing '/' FROM pc.parent_path),
                                '/',
                                1
                            ),
                            ''
                        )::int AS family_id,

                        NULLIF(
                            split_part(
                                trim(trailing '/' FROM pc.parent_path),
                                '/',
                                2
                            ),
                            ''
                        )::int AS section_id,

                        NULLIF(
                            split_part(
                                trim(trailing '/' FROM pc.parent_path),
                                '/',
                                3
                            ),
                            ''
                        )::int AS class_id,

                        NULLIF(
                            split_part(
                                trim(trailing '/' FROM pc.parent_path),
                                '/',
                                4
                            ),
                            ''
                        )::int AS brick_id

                    FROM product_category pc
                )

                SELECT

                    ROW_NUMBER() OVER () AS id,

                    rc.name AS site,

                    family.name AS family,
                    section.name AS section,
                    class.name AS class_name,
                    brick.name AS brick,
                    CASE WHEN sl.type_product = 'brand' then sl.ref else sl.name end AS barcode,
                    pc.complete_name AS article,
                    pal.name AS ageing,

                    pav.name->>'en_US' AS brand,
                    pav1.name->>'en_US' AS design,

                    sl.rs_price AS unit_rsp,
                    sl.cost_price AS cp,
                    sl.mr_price AS mrp,

                    pav2.name->>'en_US' AS description_8,

                    loyalty.promo AS promo,

                    SUM(sq.quantity) AS on_hand_qty

                FROM stock_quant sq

                JOIN stock_location loc
                    ON loc.id = sq.location_id

                LEFT JOIN stock_lot sl
                    ON sl.id = sq.lot_id

                LEFT JOIN res_company rc
                    ON rc.id = sl.company_id

                LEFT JOIN product_product pp
                    ON pp.id = sq.product_id

                LEFT JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id

                LEFT JOIN product_category pc
                    ON pc.id = pt.categ_id

                LEFT JOIN category_map cm
                    ON cm.id = pt.categ_id

                LEFT JOIN product_category family
                    ON family.id = cm.family_id

                LEFT JOIN product_category section
                    ON section.id = cm.section_id

                LEFT JOIN product_category class
                    ON class.id = cm.class_id

                LEFT JOIN product_category brick
                    ON brick.id = cm.brick_id

                LEFT JOIN product_aging_line pal
                    ON pal.id = sl.description_1

                LEFT JOIN product_attribute_value pav
                    ON pav.id = sl.category_3

                LEFT JOIN product_attribute_value pav1
                    ON pav1.id = sl.category_8

                LEFT JOIN product_attribute_value pav2
                    ON pav2.id = sl.description_8

                LEFT JOIN (
                    SELECT
                        ll.lot_id,
                        STRING_AGG(
                            DISTINCT lp.name->>'en_US',
                            ', '
                        ) AS promo

                    FROM loyalty_line ll

                    JOIN loyalty_rule lr
                        ON lr.id = ll.loyalty_id

                    JOIN loyalty_program lp
                        ON lp.id = lr.program_id

                    GROUP BY ll.lot_id
                ) loyalty
                    ON loyalty.lot_id = sl.id

                WHERE loc.usage = 'internal'
                  AND sq.company_id = 1

                GROUP BY
                    sq.product_id,
                    family.name,
                    section.name,
                    class.name,
                    brick.name,
                    pc.complete_name,
                    pal.name,
                    pav.name->>'en_US',
                    pav1.name->>'en_US',
                    sl.rs_price,
                    sl.cost_price,
                    sl.description_8,
                    pav2.name->>'en_US',
                    loyalty.promo,
                    sl.mr_price,
                    rc.name,
                    sl.type_product, sl.ref, sl.name

                HAVING SUM(sq.quantity) > 0
            );
        """)