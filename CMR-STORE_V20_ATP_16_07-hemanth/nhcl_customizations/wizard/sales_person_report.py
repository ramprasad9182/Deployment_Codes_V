from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time
from openpyxl import Workbook
from io import BytesIO
import base64


class PosSalesEmployeeReport(models.TransientModel):
    _name = 'pos.sales.employee.report'
    _description = 'POS Sales Employee Report'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True, readonly=True,
        default=lambda self: self.env.company
    )
    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    report_line_ids = fields.One2many(
        'pos.sales.employee.report.line',
        'report_id',
        string="Category Summary"
    )
    employee_id = fields.Many2one('hr.employee', string="Employee", domain=[('sale_employee', '=', 'yes')])
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Quantities')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Total Amount')
    family = fields.Many2one(
        'product.category',
        string='Family',
        domain=[('parent_id', '=', False)]
    )

    category = fields.Many2one(
        'product.category',
        string='Category',
        domain="[('parent_id', '=', family)]"
    )

    nhcl_class = fields.Many2one(
        'product.category',
        string='NHCL Class',
        domain="[('parent_id', '=', category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string='Brick',
        domain="[('parent_id', '=', nhcl_class)]"
    )
    employee_code = fields.Char(string="Employee Code")

    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.nhcl_class = False
        self.brick = False

    @api.onchange('category')
    def _onchange_category(self):
        self.nhcl_class = False
        self.brick = False

    @api.onchange('nhcl_class')
    def _onchange_nhcl_class(self):
        self.brick = False



    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.report_line_ids
            rec.total_order_quantity = sum(lines.mapped('quantity'))
            rec.total_discount_amount = sum(lines.mapped('discount'))
            rec.total_amount_total = sum(lines.mapped('total_amount'))

    def _get_category_hierarchy(self, categ):
        family = brand = cls = brick = False

        if not categ:
            return (False, False, False, False)

        path = []
        while categ:
            path.append(categ)
            categ = categ.parent_id

        path.reverse()  # Root → Leaf

        if len(path) >= 1:
            family = path[0].id
        if len(path) >= 2:
            brand = path[1].id
        if len(path) >= 3:
            cls = path[2].id
        if len(path) >= 4:
            brick = path[3].id

        return (family, brand,  cls, brick)

    # ---------------------------------------------------------
    # 🔹 GENERATE REPORT
    # ---------------------------------------------------------
    def action_generate_report(self):
        for rec in self:

            if rec.from_date > rec.to_date:
                raise ValidationError("From Date cannot be greater than To Date.")

            rec.report_line_ids.unlink()

            start = datetime.combine(rec.from_date.date(), time.min)
            end = datetime.combine(rec.to_date.date(), time.max)

            start = fields.Datetime.to_string(start)
            end = fields.Datetime.to_string(end)

            domain = [
                ('order_id.date_order', '>=', start),
                ('order_id.date_order', '<=', end),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
            ]

            # Employee filter
            if rec.employee_id:
                domain.append(('employ_id', '=', rec.employee_id.id))

            # Employee code filter
            if rec.employee_code:
                domain.append(('employ_id.barcode', '=', rec.employee_code))

            # Product hierarchy filters
            if rec.family:
                domain.append(
                    ('product_id.categ_id', 'child_of', rec.family.id)
                )

            if rec.category:
                domain.append(
                    ('product_id.categ_id', 'child_of', rec.category.id)
                )

            if rec.nhcl_class:
                domain.append(
                    ('product_id.categ_id', 'child_of', rec.nhcl_class.id)
                )

            if rec.brick:
                domain.append(
                    ('product_id.categ_id', '=', rec.brick.id)
                )

            lines = self.env['pos.order.line'].search(domain)

            summary = {}

            for line in lines:
                employee = line.employ_id
                employee_id = employee.id if employee else False

                # Get hierarchy
                family_id, brand_id, class_id, brick_id = self._get_category_hierarchy(
                    line.product_id.categ_id
                )

                key = (family_id, brand_id, class_id, brick_id, employee_id)

                if key not in summary:
                    summary[key] = {
                        'category_id': brand_id,
                        'family_id': family_id,
                        'class_id': class_id,
                        'brick_id': brick_id,
                        'employee_id': employee_id,
                        'employee_code': employee.barcode if employee else '',
                        'job_position_id': employee.job_id.id if employee else False,
                        'quantity': 0.0,
                        'total_amount': 0.0,
                        'discount': 0.0,
                    }

                summary[key]['quantity'] += line.qty
                summary[key]['total_amount'] += line.price_subtotal_incl
                summary[key]['discount'] += (
                        line.price_subtotal - line.price_subtotal_incl
                )

            rec.report_line_ids = [
                (0, 0, vals) for vals in summary.values()
            ]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Employee Report',
            'res_model': 'pos.sales.employee.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }

    def action_export_excel(self):
        self.ensure_one()

        if not self.report_line_ids:
            raise ValidationError("Please generate the report first.")

        wb = Workbook()
        ws = wb.active
        ws.title = "POS Sales Report"

        # Headers
        headers = ["Brand", "Sales Employee", "Quantity", "Total Amount"]
        ws.append(headers)

        for line in self.report_line_ids:
            ws.append([
                line.category_id.name or '',
                line.employee_id.name or '',
                line.quantity,
                line.total_amount,
            ])

        # Save file
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        file_data = base64.b64encode(buffer.read())

        attachment = self.env['ir.attachment'].create({
            'name': 'POS_Sales_Employee_Report.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_print_pdf(self):
        return self.env.ref('nhcl_customizations.pos_sales_employee_report_pdf').report_action(self)


    def action_to_reset(self):
        for rec in self:
            rec.report_line_ids.unlink()

    def action_view_sale_employee_detailed_report(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Employee Report',
            'res_model': 'pos.sales.employee.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }


class PosSalesEmployeeReportLine(models.TransientModel):
    _name = 'pos.sales.employee.report.line'
    _description = 'POS Sales Employee Report Line'

    report_id = fields.Many2one('pos.sales.employee.report',string="Report",ondelete='cascade')
    category_id = fields.Many2one('product.category',string="Category")
    family_id = fields.Many2one('product.category',string="Family")
    class_id = fields.Many2one('product.category',string="Class")
    brick_id = fields.Many2one('product.category',string="Brick")
    employee_id = fields.Many2one('hr.employee',string="Sales Employee")
    employee_code = fields.Char(string="Employee Code")
    job_position_id = fields.Many2one('hr.job',string="Job Position")
    quantity = fields.Float(string="Total Quantity")
    total_amount = fields.Float(string="Total Amount")
    discount = fields.Float(string="Discount")