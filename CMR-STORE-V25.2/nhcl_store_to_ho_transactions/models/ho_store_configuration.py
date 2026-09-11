from odoo import models
from datetime import datetime


class HoStoreMaster(models.Model):
    """Created nhcl.ho.store.master class to add fields and functions"""
    _inherit = "nhcl.ho.store.master"

    def create_cmr_transaction_replication_log(self, model_name, record_id, record_name, status_code, function_required, status,
                                               details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.transaction.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_source_id': ho_id.nhcl_store_id,
            'nhcl_source_name': ho_id.nhcl_store_name,
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name,
            'nhcl_model': model_name,
            'nhcl_record_id': record_id,
            'nhcl_record_name': record_name,
            'nhcl_status_code': status_code,
            'nhcl_function_required': function_required,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.transaction.replication.log'].create(vals)


    def create_cmr_transaction_server_replication_log(self, status, details_status):
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.transaction.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.transaction.replication.log'].create(vals)