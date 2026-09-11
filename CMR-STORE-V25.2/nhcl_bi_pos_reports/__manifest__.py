# -*- coding: utf-8 -*-

{
	"name" : "NHCL ALL POS Reports in Odoo (POS BOX Compatible)",
	"version" : "17.0.0.0",
	"category" : "Point of Sale",
	"depends" : ['base','sale','point_of_sale'],
	"author": "New Horizons CyberSoft Ltd",
	'company': 'New Horizons CyberSoft Ltd',
    'maintainer': 'New Horizons CyberSoft Ltd',
	'summary': 'All in one pos reports Print pos session report pos sales summery report pos sales reports point of sales reports pos X Report pos z report pos payment summary reports pos Inventory audit report pos Order summary report pos Posted Session POS Profit Report',
	"description": """
	odoo Print POS Reports print pos reports odoo all in one pos reports
    odoo point of sales reports pos reports print pos report print
	odoo pos sales summary report pos summary report pos Session and Inventory audit report
    odoo pos audit report pos Product summary report
     odoo pos sessions reports pos session reports pos User wise sales summary reports
     odoo pos payment summary reports summary reports in POS
     odoo point of sales summary reports point of sales reports pos user reports
     odoo point of sales all reports pos products reports pos audit reports audit reports pos 
	odoo pos Inventory audit reports pos Inventory reports Product summary report pos 
	odoo Print point of sales Reports print point of sales reports odoo all in one point of sales reports
    odoo point of sale reports point of sales reports print point of sales report print
	odoo point of sale summary report point of sales summary report point of sales Session and Inventory audit report
    odoo point of sales audit report point of sale Product summary report
     odoo point of sales sessions reports point of sales session reports point of sales User wise sales summary reports
     odoo pos payment summary reports summary reports in POS
     odoo point of sales summary reports point of sales reports point of sales user reports
     odoo point of sale all reports point of sales products reports point of sales audit reports audit reports point of sales 
	odoo point of sales Inventory audit reports point of sales Inventory reports Product summary report point of sales 

	""",
	"website" : "https://www.nhclindia.com",
	"currency": "INR",
	"data": [
		'security/ir.model.access.csv',
		'views/pos_reports.xml',
		'views/product_view.xml',
		'wizard/pos_sale_summary.xml',
		'wizard/sales_summary_report.xml',
		'wizard/x_report_view.xml',
		'wizard/z_report_view.xml',
		'wizard/top_selling.xml',
		'wizard/top_selling_report.xml',
		'wizard/profit_loss_report.xml',
		'wizard/pos_payment_report.xml',
		'wizard/profit_loss.xml',
		'wizard/pos_payment.xml',
		'wizard/user_wise_sales_details_report.xml',
		'wizard/highest_selling_product_report_view.xml',
		'wizard/shop_wise_sale_report.xml',
		'wizard/pos_tax_summary_report.xml',
		'report/user_wise_sales_detail_report_abstract.xml',
		'report/highest_selling_product_report_template.xml',
		'report/shop_wise_detail_report.xml',
		'report/pos_tax_summary_detail_report.xml',
	],
	'assets': {
		'point_of_sale._assets_pos': [
			'nhcl_bi_pos_reports/static/src/css/reports.css',
			'nhcl_bi_pos_reports/static/src/js/models.js',
			'nhcl_bi_pos_reports/static/src/js/AuditReport/ReportLocationButtonWidget.js',
			'nhcl_bi_pos_reports/static/src/js/AuditReport/PopupLocationWidget.js',
			'nhcl_bi_pos_reports/static/src/js/AuditReport/LocationReceiptScreen.js',
			'nhcl_bi_pos_reports/static/src/js/AuditReport/LocationReceipt.js',
			'nhcl_bi_pos_reports/static/src/js/CategorySummary/ReportCategoryButtonWidget.js',
			'nhcl_bi_pos_reports/static/src/js/CategorySummary/PopupCategoryWidget.js',
			'nhcl_bi_pos_reports/static/src/js/CategorySummary/CategoryReceiptWidget.js',
			'nhcl_bi_pos_reports/static/src/js/CategorySummary/XMLPosCategorySummaryReceipt.js',
			'nhcl_bi_pos_reports/static/src/js/OrderSummary/ReportOrderButtonWidget.js',
			'nhcl_bi_pos_reports/static/src/js/OrderSummary/PopupOrderWidget.js',
			'nhcl_bi_pos_reports/static/src/js/OrderSummary/OrderReceiptWidget.js',
			'nhcl_bi_pos_reports/static/src/js/OrderSummary/XMLPosOrderSummaryReceipt.js',
			'nhcl_bi_pos_reports/static/src/js/PaymentReport/ReportPaymentButtonWidget.js',
			'nhcl_bi_pos_reports/static/src/js/PaymentReport/PaymentSummaryPopup.js',
			'nhcl_bi_pos_reports/static/src/js/PaymentReport/PaymentReceiptWidget.js',
			'nhcl_bi_pos_reports/static/src/js/PaymentReport/XMLPosPaymentSummaryReceipt.js',
			'nhcl_bi_pos_reports/static/src/js/ReportProductButton/ReportProductButtonWidget.js',
			'nhcl_bi_pos_reports/static/src/js/ReportProductButton/PopupProductWidget.js',
			'nhcl_bi_pos_reports/static/src/js/ReportProductButton/ProductReceiptWidget.js',
			'nhcl_bi_pos_reports/static/src/js/ReportProductButton/XMLPosProductSummaryReceipt.js',
			'nhcl_bi_pos_reports/static/src/xml/AuditReport.xml',
			'nhcl_bi_pos_reports/static/src/xml/CategoryReport.xml',
			'nhcl_bi_pos_reports/static/src/xml/OrderReport.xml',
			'nhcl_bi_pos_reports/static/src/xml/PaymentReport.xml',
			'nhcl_bi_pos_reports/static/src/xml/ProductReport.xml',
		],
	},
	"auto_install": False,
	"installable": True,
	"images":['static/description/Banner.gif'],
	"live_test_url":'https://youtu.be/Y5t_EZJxymY',
	'license': 'OPL-1',
}
