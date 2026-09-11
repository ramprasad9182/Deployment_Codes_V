from odoo import models, fields, api, _
from datetime import datetime, time, timedelta, date
import pytz


class AccountAccount(models.Model):
    _inherit = "account.account"


    @api.model
    def get_processed_account(self):
        processed_account = self.env['account.account'].search_count([('update_replication', '=', True)])
        return {
            'processed_account': f"{processed_account:,}",
        }

    @api.model
    def get_total_account(self):
        total_account = self.env['account.account'].search_count([])
        return {
            'total_account': f"{total_account:,}",
        }

class AccountTax(models.Model):
    _inherit = "account.tax"


    @api.model
    def get_processed_tax(self):
        processed_tax = self.search_count([('update_replication', '=', True)])
        return {
            'processed_tax': f"{processed_tax:,}",
        }

    @api.model
    def get_total_tax(self):
        total_tax = self.search_count([])
        return {
            'total_tax': f"{total_tax:,}",
        }

class ProductAttribute(models.Model):
    _inherit = "product.attribute"


    @api.model
    def get_processed_attribute(self):
        processed_attribute = self.search_count([('update_replication', '=', True)])
        return {
            'processed_attribute': f"{processed_attribute:,}",
        }

    @api.model
    def get_total_attribute(self):
        total_attribute = self.search_count([])
        return {
            'total_attribute': f"{total_attribute:,}",
        }

class ProductTemplate(models.Model):
    _inherit = 'product.template'


    @api.model
    def get_processed_template(self):
        processed_template = self.env['product.template'].search_count([('update_replication', '=', True)])
        return {
            'processed_template': f"{processed_template:,}",
        }

    @api.model
    def get_total_template(self):
        total_template = self.search_count([])
        return {
            'total_template': f"{total_template:,}",
        }

class ProductCategory(models.Model):
    _inherit = "product.category"


    @api.model
    def get_processed_category(self):
        processed_category = self.search_count([('update_replication', '=', True)])
        return {
            'processed_category': f"{processed_category:,}",
        }

    @api.model
    def get_total_category(self):
        total_category = self.search_count([])
        return {
            'total_category': f"{total_category:,}",
        }

class ProductProduct(models.Model):
    _inherit = 'product.product'


    @api.model
    def get_processed_product(self):
        processed_product = self.search_count([('update_replication', '=', True)])
        return {
            'processed_product': f"{processed_product:,}",
        }

    @api.model
    def get_total_product(self):
        total_product = self.search_count([])
        return {
            'total_product': f"{total_product:,}",
        }

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def get_processed_employee(self):
        processed_employee = self.search_count([('update_replication', '=', True)])
        return {
            'processed_employee': f"{processed_employee:,}",
        }

    @api.model
    def get_total_employee(self):
        total_employee = self.search_count([])
        return {
            'total_employee': f"{total_employee:,}",
        }

class Contact(models.Model):
    _inherit = "res.partner"


    @api.model
    def get_processed_partner(self):
        processed_partner = self.search_count([('update_replication', '=', True)])
        return {
            'processed_partner': f"{processed_partner:,}",
        }

    @api.model
    def get_total_partner(self):
        total_partner = self.search_count([])
        return {
            'total_partner': f"{total_partner:,}",
        }

class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"


    @api.model
    def get_processed_loyalty(self):
        processed_loyalty = self.search_count([('update_replication', '=', True)])
        return {
            'processed_loyalty': f"{processed_loyalty:,}",
        }

    @api.model
    def get_total_loyalty(self):
        total_loyalty = self.search_count([])
        return {
            'total_loyalty': f"{total_loyalty:,}",
        }

class Users(models.Model):
    _inherit = 'res.users'


    @api.model
    def get_processed_users(self):
        processed_users = self.search_count([('update_replication', '=', True)])
        return {
            'processed_users': f"{processed_users:,}",
        }

    @api.model
    def get_total_users(self):
        total_users = self.search_count([])
        return {
            'total_users': f"{total_users:,}",
        }

class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    @api.model
    def TotalDeliveries(self):
        TotalDeliveries = self.search_count([
            ('is_wave', '=', False),
            ('transfer_type', '=', 'out'),
            ('company_id.nhcl_company_bool', '=', True),
            ('state', '=', 'done'),
        ])

        return {'TotalDeliveries': f"{TotalDeliveries:,}"}

    @api.model
    def action_total_deliveries(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Total Deliveries',
            'res_model': 'stock.picking.batch',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [
                ('is_wave', '=', False),
                ('transfer_type', '=', 'out'),
                ('company_id.nhcl_company_bool', '=', True),
                ('state', '=', 'done'),
            ],
            'context': {'create': False,
                        'default_transfer_type': 'in',},
        }

    @api.model
    def totalBatches(self):
        totalBatches = self.search_count([
            ('is_wave', '=', False),
            ('transfer_type', '=', 'in'),
            ('company_id.nhcl_company_bool', '=', False),
            ('state', '=', 'done')
        ])

        return {'totalBatches': f"{totalBatches:,}"}

    @api.model
    def action_total_batches(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Total Batches',
            'res_model': 'stock.picking.batch',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [
                ('is_wave', '=', False),
                ('transfer_type', '=', 'in'),
                ('company_id.nhcl_company_bool', '=', False),
                ('state', '=', 'done')
            ],
            'context': {'create': False,
                        'default_transfer_type': 'in',},
        }




class HoStoreMaster(models.Model):
    _inherit = "nhcl.ho.store.master"


    @api.model
    def get_total_liveSync(self):
        total_liveSync = self.search_count([])
        return {
            'total_liveSync': f"{total_liveSync:,}",
        }

    @api.model
    def action_total_liveSync(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Total Configured Store',
            'res_model': 'nhcl.ho.store.master',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [],
            'context': {'create': False},
        }


    @api.model
    def get_total_liveStore(self):
        total_liveStore = self.search_count([('nhcl_active', '=', True)])
        return {
            'total_liveStore': f"{total_liveStore:,}",
        }

    @api.model
    def action_total_liveStore(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Total Live Store',
            'res_model': 'nhcl.ho.store.master',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('nhcl_active', '=', True)],
            'context': {'create': False},
        }



# class TransactionReplicationLog(models.Model):
#     _inherit = 'nhcl.transaction.replication.log'
#
#
#
#     @api.model
#     def PendingDeliveries(self):
#         PendingDeliveries = self.env['nhcl.transaction.replication.log'].search_count([
#             ('nhcl_model', 'ilike', 'stock.picking.batch'),
#             ('nhcl_status', '=', 'failure'),
#         ])
#         print('===> PendingDeliveries',PendingDeliveries)
#         return {'PendingDeliveries': f"{PendingDeliveries:,}"}
#
#     @api.model
#     def action_pending_deliveries(self):
#         return {
#             'type': 'ir.actions.act_window',
#             'name': 'Pending Deliveries',
#             'res_model': 'nhcl.transaction.replication.log',
#             'view_mode': 'list,form',
#             'views': [(False, 'list'), (False, 'form')],
#             'domain': [
#                 ('nhcl_model', '=', 'stock.picking.batch'),
#                 ('nhcl_status', '=', 'failure'),
#             ],
#             'context': {'create': False},
#         }
#
#     @api.model
#     def ProcessedDeliveries(self):
#         ProcessedDeliveries = self.env['nhcl.transaction.replication.log'].search_count([
#             ('nhcl_model', 'ilike', 'stock picking batch'),
#             ('nhcl_status', '=', 'success'),
#         ])
#
#         return {'ProcessedDeliveries': f"{ProcessedDeliveries:,}"}
#
#     @api.model
#     def action_processed_deliveries(self):
#         return {
#             'type': 'ir.actions.act_window',
#             'name': 'Processed Deliveries',
#             'res_model': 'nhcl.transaction.replication.log',
#             'view_mode': 'list,form',
#             'views': [(False, 'list'), (False, 'form')],
#             'domain': [
#                 ('nhcl_model', '=', 'stock.picking.batch'),
#                 ('nhcl_status', '=', 'success'),
#             ],
#             'context': {'create': False},
#         }
#
#     def _get_today_range(self):
#         user_tz = self.env.user.tz or 'UTC'
#         tz = pytz.timezone(user_tz)
#
#         now = fields.Datetime.now()
#         now_local = fields.Datetime.context_timestamp(self, now)
#
#         start_local = datetime.combine(now_local.date(), time.min)
#         end_local = start_local + timedelta(days=1)
#
#         # Convert to UTC
#         start_utc = tz.localize(start_local).astimezone(pytz.UTC)
#         end_utc = tz.localize(end_local).astimezone(pytz.UTC)
#
#         return fields.Datetime.to_string(start_utc), fields.Datetime.to_string(end_utc)
#
#     def _get_today_range(self):
#         user_now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
#         today_date = user_now.date()
#
#         start = datetime.combine(today_date, time.min)
#         end = start + timedelta(days=1)
#
#         return fields.Datetime.to_string(start), fields.Datetime.to_string(end)
#
#     @api.model
#     def transactionNotProcessed(self):
#         transactionNotProcessed = self.search_count([
#             ('nhcl_status', '=', 'failure')
#         ])
#         return {'transactionNotProcessed': f"{transactionNotProcessed:,}"}
#
#     @api.model
#     def transactionToday(self):
#         start, end = self._get_today_range()
#
#         transactionToday = self.search_count([
#             ('nhcl_status', '=', 'success'),
#             ('nhcl_date_of_log', '>=', start),
#             ('nhcl_date_of_log', '<', end),
#         ])
#
#         return {'transactionToday': f"{transactionToday:,}"}
#
#     @api.model
#     def transactionNotToday(self):
#         start, end = self._get_today_range()
#
#         transactionNotToday = self.search_count([
#             ('nhcl_status', '=', 'failure'),
#             ('nhcl_date_of_log', '>=', start),
#             ('nhcl_date_of_log', '<', end),
#         ])
#
#         return {'transactionNotToday': f"{transactionNotToday:,}"}
#
#     @api.model
#     def action_failed_today(self):
#         start, end = self._get_today_range()
#
#         return {
#             'type': 'ir.actions.act_window',
#             'name': 'Transactions Not Processed Today',
#             'res_model': 'nhcl.transaction.replication.log',
#             'view_mode': 'list,form',
#             'views': [(False, 'list'), (False, 'form')],  # IMPORTANT
#             'domain': [
#                 ('nhcl_status', '=', 'failure'),
#                 ('nhcl_date_of_log', '>=', start),
#                 ('nhcl_date_of_log', '<', end),
#             ],
#             'context': {'create': False},
#         }
#
#     @api.model
#     def get_total_transactionEvent(self):
#         total_transactionEvent = self.search_count([])
#         return {
#             'total_transactionEvent': f"{total_transactionEvent:,}",
#         }
#
#     @api.model
#     def get_total_transactionToday(self):
#         # Get today's date
#         today_date = date.today()
#         # Count records where nhcl_date_of_log equals today's date
#         total_transactionToday = self.search_count([('nhcl_date_of_log', '=', today_date)])
#         return {
#             'total_transactionToday': f"{total_transactionToday:,}",
#         }



# class OldStoreReplicationLog(models.Model):
#     _inherit = 'nhcl.old.store.replication.log'
#
#
#     @api.model
#     def get_pending_account(self):
#         pending_account = self.env['nhcl.old.store.replication.log'].search_count([
#             ('nhcl_model', 'ilike', 'account.account'),
#             ('nhcl_status', '=', 'failure')
#         ])
#
#         return {
#             'pending_account': f"{pending_account:,}",
#         }
#
#     @api.model
#     def get_pending_tax(self):
#         pending_tax = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'tax'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_tax': f"{pending_tax:,}",
#         }
#
#     @api.model
#     def get_pending_attribute(self):
#         pending_attribute = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'attribute'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_attribute': f"{pending_attribute:,}",
#         }
#
#     @api.model
#     def get_pending_category(self):
#         pending_category = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'category'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_category': f"{pending_category:,}",
#         }
#
#     @api.model
#     def get_pending_template(self):
#         pending_template = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'template'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_template': f"{pending_template:,}",
#         }
#
#     @api.model
#     def get_pending_product(self):
#         pending_product = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'variant'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_product': f"{pending_product:,}",
#         }
#
#     @api.model
#     def get_pending_employee(self):
#         pending_employee = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'employee'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_employee': f"{pending_employee:,}",
#         }
#
#     @api.model
#     def get_pending_partner(self):
#         pending_partner = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'user'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_partner': f"{pending_partner:,}",
#         }
#
#     @api.model
#     def get_pending_loyalty(self):
#         pending_loyalty = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'loyalty'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_loyalty': f"{pending_loyalty:,}",
#         }
#
#     @api.model
#     def get_pending_users(self):
#         pending_users = self.env['nhcl.old.store.replication.log'].search_count([('nhcl_model', 'ilike', 'user'),
#             ('nhcl_status', '=', 'failure')])
#         return {
#             'pending_users': f"{pending_users:,}",
#         }
#
#
#
#     @api.model
#     def get_total_processedEvent(self):
#         total_processedEvent = self.search_count([])
#         return {
#             'total_processedEvent': f"{total_processedEvent:,}",
#         }
#
#     @api.model
#     def get_total_processedToday(self):
#         # Get today's date
#         today_date = date.today()
#         # Count records where nhcl_date_of_log equals today's date
#         total_processedToday = self.search_count([('nhcl_date_of_log', '=', today_date)])
#         return {
#             'total_processedToday': f"{total_processedToday:,}",
#         }



class JobInitiatedStatusLogDashboard(models.TransientModel):
    _name = 'nhcl.initiated.status.dashboard.log'
    _description = "Job Initiated Status Log"
    _order = 'nhcl_date_of_log desc'

    nhcl_serial_no = fields.Char('S.No')
    nhcl_date_of_log = fields.Datetime('Date of Log')
    nhcl_job_name = fields.Char(string='Job Name')
    nhcl_status = fields.Selection([('success', 'Success'), ('failure', 'Failure')], default=False, string='Status')
    nhcl_details_status = fields.Char('Response')

    def job_status_log(self):

        # Delete old dashboard records
        self.env['nhcl.initiated.status.dashboard.log'].search([]).unlink()

        # Required job names
        job_names = [
            'Missing Serial Number Transaction',
            'POS Order Live Sync'
        ]

        dashboard_vals = []

        for job in job_names:

            # Get latest record for each job
            latest_record = self.env['nhcl.initiated.status.log'].search(
                [('nhcl_job_name', '=', job)],
                order='nhcl_date_of_log desc',
                limit=1
            )

            if latest_record:
                dashboard_vals.append({
                    'nhcl_serial_no': latest_record.nhcl_serial_no,
                    'nhcl_date_of_log': latest_record.nhcl_date_of_log,
                    'nhcl_job_name': latest_record.nhcl_job_name,
                    'nhcl_status': latest_record.nhcl_status,
                    'nhcl_details_status': latest_record.nhcl_details_status,
                })

        # Create dashboard records
        if dashboard_vals:
            self.env['nhcl.initiated.status.dashboard.log'].create(dashboard_vals)

        # Return action
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Initiated Status Dashboard',
            'res_model': 'nhcl.initiated.status.dashboard.log',
            'view_mode': 'tree',
            'target': 'current',
        }
