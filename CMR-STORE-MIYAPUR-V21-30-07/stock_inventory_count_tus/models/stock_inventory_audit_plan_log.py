from odoo import models,fields

class AuditReplicationLog(models.Model):
    _name = 'nhcl.audit.replication.log'
    _description = 'NHCL Audit Replication Log'

    nhcl_serial_no = fields.Char('S.No', readonly=True,copy=False)
    nhcl_date_of_log = fields.Datetime('Date of Log')
    nhcl_source_id = fields.Char("Source Id")
    nhcl_source_name = fields.Char(string='Source Name')
    nhcl_destination_id = fields.Char("Destination Id")
    nhcl_destination_name = fields.Char(string='Destination Name')
    nhcl_record_id = fields.Integer('Record Id')
    nhcl_function_required = fields.Selection([('add', 'ADD'), ('update', 'Update')], default=False,
                                              string="Function Required")
    nhcl_status = fields.Selection([('success', 'Success'), ('failure', 'Failure')], default=False, string='Status')
    nhcl_details_status = fields.Char('Response')
    nhcl_model = fields.Char('Model')
    nhcl_status_code = fields.Char('Status Code')