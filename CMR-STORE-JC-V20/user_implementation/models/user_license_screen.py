from odoo import models, fields,api
from cryptography.fernet import Fernet
import base64
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import zlib
import re


class LicenseKey(models.Model):
    _name = 'license.key'
    _description = 'License Key'
    _rec_name = 'sequence'


    cashier_count = fields.Integer(string="Cashier Count")
    backend_count = fields.Integer(string="Backend Count")
    # sales_person_count = fields.Integer(string="Salesperson Count")
    expiry_date = fields.Date(string="Expiry Date")
    user_type = fields.Char(string="User Type")
    email = fields.Char(string="Email")
    store_name = fields.Char(string="Store Name")  # Optional for storing store_id string
    doc_number = fields.Char(string="Document Number")
    doc_date = fields.Date(string="Document Date")

    sequence = fields.Char(string="License Number", readonly=True, copy=False, default='New')

    license_counts = fields.Integer(string="License Count")
    is_used = fields.Boolean(string="Used")
    is_verified = fields.Boolean(string="User verified",default=True)
    is_create = fields.Boolean(string="User create", default=False)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company.id
    )
    store_id = fields.Many2one('nhcl.ho.store.master', string='Company')
    email = fields.Char(string='Emails')
    license_key = fields.Char(string="Import License Key",required=True)
    note = fields.Text(string="License Key Details")
    license_line_ids = fields.One2many('license.key.line', 'license_id', string="License Lines")
    is_success = fields.Boolean(string="success",default=False)
    # _sql_constraints = [
    #     ('unique_license_key_note', 'unique(license_key)',
    #      'This License Key and Encrypted Data combination must be unique.')
    # ]



    @api.constrains('license_key')
    def _check_unique_license_key_note(self):
        print("************************")
        for record in self:
            if record.license_key:
                duplicates = self.search([
                    ('license_key', '=', record.license_key),
                    ('id', '!=', record.id)
                ], limit=1)
                if duplicates:
                    raise ValidationError("This License Key was already used.")

    def action_for_create_users(self):
        for record in self:
            used_employees = []

            for line in record.license_line_ids:
                if line.status == 'created':
                    continue

                if line.user_type in ['cashier', 'backend']:
                    # Create user
                    employee = line.employee_id.sudo()
                    if not employee.work_email:
                        raise ValidationError("Employee must have work email")
                    user = self.env['res.users'].search([('login', '=', employee.work_email)], limit=1)
                    if not user:
                        user = self.env['res.users'].create({
                            'name': employee.name,
                            'login': employee.work_email,
                            'expiry_date': line.to_date,
                            'user_license_id': line.id,
                        })
                    employee.write({'user_id': user.id})
                    line.status = 'created'
                elif line.user_type == 'salesperson':
                    # Just mark status if employee is selected
                    if not line.employee_id:
                        raise ValidationError(f"Please select an employee for salesperson in line: {line.season_name}")
                    line.status = 'employee_created'
                    used_employees.append(line.employee_id.id)

            record.is_verified = True

    def action_for_create_button_wizard(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm User Creation',
            'res_model': 'license.key.create.users.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_users_license_id': self.id,
            },
        }

    def action_for_decrypt_license_key(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm User Creation',
            'res_model': 'license.key.user.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_license_id': self.id,
            },
        }

    def _get_next_sequence(self, prefix):
        # Fetch existing season_names like 'CA0001', 'SP0002', etc.
        existing = self.env['license.key.line'].search([('season_name', 'like', f"{prefix}%")])
        max_num = 0
        for rec in existing:
            match = re.match(rf"{prefix}(\d+)", rec.season_name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        return max_num + 1

    def _create_license_lines_from_decrypted_data(self):
        self.ensure_one()

        # Clear previous lines
        self.license_line_ids.unlink()

        # Initialize counters for each type
        next_cashier = self._get_next_sequence('CA')
        next_backend = self._get_next_sequence('OD')
        next_salesperson = self._get_next_sequence('SP')

        s_no = 1

        # Cashiers
        for _ in range(self.cashier_count):
            self.env['license.key.line'].create({
                's_no': s_no,
                'season_name': f"CA{str(next_cashier).zfill(4)}",
                'user_type': 'cashier',
                'license_id': self.id,
                'from_date': self.doc_date,
                'to_date': self.expiry_date,
                'status': 'waiting',
            })
            next_cashier += 1
            s_no += 1

        # Backends
        for _ in range(self.backend_count):
            self.env['license.key.line'].create({
                's_no': s_no,
                'season_name': f"OD{str(next_backend).zfill(4)}",
                'user_type': 'backend',
                'license_id': self.id,
                'from_date': self.doc_date,
                'to_date': self.expiry_date,
                'status': 'waiting',
            })
            next_backend += 1
            s_no += 1

        # Salespersons
        # for _ in range(self.sales_person_count):
        #     self.env['license.key.line'].create({
        #         's_no': s_no,
        #         'season_name': f"SP{str(next_salesperson).zfill(4)}",
        #         'user_type': 'salesperson',
        #         'license_id': self.id,
        #         'from_date': self.doc_date,
        #         'to_date': self.expiry_date,
        #         'status': 'waiting',
        #     })
        #     next_salesperson += 1
        #     s_no += 1

        self.is_used = True
        self.is_verified = False
        self.is_create = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            license_key = vals.get('license_key')

            if license_key:
                try:
                    # 🔐 Decryption
                    key_b64, encrypted_data_b64 = license_key.split(":")
                    key = base64.urlsafe_b64decode(key_b64)
                    encrypted_data = base64.urlsafe_b64decode(encrypted_data_b64)

                    fernet = Fernet(key)
                    decrypted_compressed = fernet.decrypt(encrypted_data)
                    decrypted_data = zlib.decompress(decrypted_compressed).decode()

                    (
                        doc_number,
                        doc_date,
                        user_type,
                        store_name_str,
                        email,
                        license_count,
                        cashier_count,
                        backend_count,
                        expiry_date
                    ) = decrypted_data.split("|")

                    # 📅 Date parsing
                    doc_date = datetime.strptime(doc_date, "%Y-%m-%d").date()
                    expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()

                    # ❌ Validations
                    if expiry_date < fields.Date.today():
                        raise ValidationError("License key is expired.")

                    if int(license_count) <= 0:
                        raise ValidationError("No user licenses provided.")

                    if store_name_str.strip().lower() != self.env.company.name.strip().lower():
                        raise ValidationError("License key store does not match your current store.")

                    # ✅ Assign values
                    vals.update({
                        'doc_number': doc_number,
                        'doc_date': doc_date,
                        'expiry_date': expiry_date,
                        'user_type': user_type,
                        'email': email,
                        'license_counts': int(license_count),
                        'cashier_count': int(cashier_count),
                        'backend_count': int(backend_count),
                        'is_success': True,
                    })

                except Exception as e:
                    raise ValidationError(f"License key validation failed: {str(e)}")

            # 🔢 Sequence generation
            if vals.get('sequence', 'New') == 'New' and vals.get('is_success'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('license.key.seq') or 'New'

        return super().create(vals_list)

    # def action_for_decrypt_license_key(self):
    #     for record in self:
    #         if not record.license_key:
    #             raise ValidationError("No license key or encryption key found.")
    # ('salesperson', 'Salesperson'),
    #         fernet = Fernet(record.license_key.encode())
    #         try:
    #             decrypted_data = fernet.decrypt(record.license_key.encode()).decode()
    #             doc_number, doc_date, user_type, company_id, email, license_count = decrypted_data.split("|")
    #
    #             expiry_date = datetime.strptime(doc_date, "%Y-%m-%d").date()
    #             if expiry_date < datetime.today().date():
    #                 raise ValidationError("License key is expired.")
    #
    #
    #             record.doc_number = doc_number
    #             record.doc_date = expiry_date
    #             record.user_type = user_type
    #             record.company_id = int(company_id)
    #             record.email = email
    #             record.license_count = int(license_count)
    #
    #             self.create_users_based_on_license(record)
    #
    #         except Exception as e:
    #             raise ValidationError(f"Decryption failed: {str(e)}")
    #
    #     # def create_users_based_on_license(self, record):
    #     #     for i in range(record.license_count):
    #     #         self.env['res.users'].create({
    #     #             'name': f"Licensed User {i + 1}",
    #     #             'login': f"{record.email.split('@')[0]}{i + 1}@{record.email.split('@')[1]}",
    #     #             'company_id': record.company_id.id,
    #     #             'email': record.email,
    #     #             # Add other defaults as needed
    #     #         })



class LicenseKeyLine(models.Model):
    _name = 'license.key.line'
    _description = 'License Key Line'

    license_id = fields.Many2one('license.key', string='License Reference', ondelete='cascade')
    s_no = fields.Integer(string='S.No')
    season_name = fields.Char(string='User Name')
    from_date = fields.Date(string='Request Date')
    to_date = fields.Date(string='Expiry Date')
    status = fields.Selection([
        ('waiting', 'Waiting for User Creation'),
        ('created', 'User Created'),('employee_created','Employee Created')
    ], string="Status", readonly=True, copy=False,default='waiting')
    user_type = fields.Selection([
        ('cashier', 'Cashier'),
        ('backend', 'Backend User'),
    ], string='User Type')
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        domain="[('sale_employee', '=', 'no'), ('user_id', '=', False)]"
    )
    employee_email = fields.Char(string='Email')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.employee_email = self.employee_id.work_email

        if self.license_id:
            used_employee_ids = self.license_id.license_line_ids.filtered(lambda l: l.id != self.id).mapped(
                'employee_id.id')
            return {
                'domain': {
                    'employee_id': [
                        ('sale_employee', '=', 'no'),
                        ('user_id', '=', False),
                        ('id', 'not in', used_employee_ids)
                    ]
                }
            }

    @api.constrains('employee_id')
    def _check_employee_used_once_globally(self):
        for line in self:
            if line.employee_id:
                duplicates = self.env['license.key.line'].search([
                    ('employee_id', '=', line.employee_id.id),
                    ('id', '!=', line.id)
                ])
                if duplicates:
                    raise ValidationError("This employee is already assigned in another license.")






