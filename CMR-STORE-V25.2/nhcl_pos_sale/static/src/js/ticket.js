/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

import { Order } from "@point_of_sale/app/store/models";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { parseFloat } from "@web/views/fields/parsers";
import { _t } from "@web/core/l10n/translation";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";

import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { InvoiceButton } from "@point_of_sale/app/screens/ticket_screen/invoice_button/invoice_button";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { CenteredIcon } from "@point_of_sale/app/generic_components/centered_icon/centered_icon";
import { ReprintReceiptButton } from "@point_of_sale/app/screens/ticket_screen/reprint_receipt_button/reprint_receipt_button";
import { SearchBar } from "@point_of_sale/app/screens/ticket_screen/search_bar/search_bar";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component, onMounted, useState } from "@odoo/owl";
import { Numpad } from "@point_of_sale/app/generic_components/numpad/numpad";

const { DateTime } = luxon;

//
//patch(TicketScreen.prototype, {
//
//
//    async onDoRefund() {
//
//        const order = this.getSelectedOrder();
//
//         const orderDate = new Date(
//        order.date_order.year,
//        order.date_order.month - 1, // JavaScript months are 0-based
//        order.date_order.day,
//        order.date_order.hour,
//        order.date_order.minute,
//        order.date_order.second,
//        order.date_order.millisecond
//    );
//
//    // Get the current date
//    const currentDate = new Date();
//
//    // Add 14 days to the order date
//    const thresholdDate = new Date(orderDate);
//    thresholdDate.setDate(orderDate.getDate() + 2);
//
//    // Check if the current date has crossed the threshold
//    if (currentDate > thresholdDate) {
//        const approvalGranted = await this.approve();
//        if (!approvalGranted) {
//            // Approval denied, exit the function
//            return;
//        }
//    }
//
//        if (order && this._doesOrderHaveSoleItem(order)) {
//            if (!this._prepareAutoRefundOnOrder(order)) {
//                // Don't proceed on refund if preparation returned false.
//                return;
//            }
//        }
//
//        if (!order) {
//            this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
//            return;
//        }
//
//        const partner = order.get_partner();
//
//        const allToRefundDetails = this._getRefundableDetails(partner);
//        if (allToRefundDetails.length == 0) {
//            this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
//            return;
//        }
//
//        const invoicedOrderIds = new Set(
//            allToRefundDetails
//                .filter(detail => this._state.syncedOrders.cache[detail.orderline.orderBackendId].state === "invoiced")
//                .map(detail => detail.orderline.orderBackendId)
//        );
//
//        if (invoicedOrderIds.size > 1) {
//            this.popup.add(ErrorPopup, {
//                title: _t('Multiple Invoiced Orders Selected'),
//                body: _t('You have selected orderlines from multiple invoiced orders. To proceed refund, please select orderlines from the same invoiced order.')
//            });
//            return;
//        }
//
//        // The order that will contain the refund orderlines.
//        // Use the destinationOrder from props if the order to refund has the same
//        // partner as the destinationOrder.
//        const destinationOrder =
//            this.props.destinationOrder &&
//            partner === this.props.destinationOrder.get_partner() &&
//            !this.pos.doNotAllowRefundAndSales()
//                ? this.props.destinationOrder
//                : this._getEmptyOrder(partner);
//
//        // Add orderline for each toRefundDetail to the destinationOrder.
//        const originalToDestinationLineMap = new Map();
//        for (const refundDetail of allToRefundDetails) {
//            const product = this.pos.db.get_product_by_id(refundDetail.orderline.productId);
//            const options = this._prepareRefundOrderlineOptions(refundDetail);
//            const discproduct = this.pos.db.get_product_by_id(this.pos.config.discount_product_id[0]);
//            let gdiscount = 0
//            if (product == discproduct){
//             let qty = 0
//            for (const refund_line of allToRefundDetails) {
//            if (refund_line['orderline']['tax_ids'][0] === options['tax_ids'][0] && refund_line['orderline'].price>0)
//            {
//             qty +=refund_line['orderline'].price - (refund_line['orderline'].price*(refund_line['orderline'].discount*0.01))
//            }
//            }
//           options.price =  qty
//            }
//            if (order.orderlines){
//            gdiscount = order.orderlines[0].gdiscount
//            }
//             options.price =  -(options.price *(gdiscount*0.01))
//
////            await destinationOrder.add_product(product, options);
////            refundDetail.destinationOrderUid = destinationOrder.uid;
//            const newOrderline = await destinationOrder.add_product(product, options);
//            newOrderline.set_gdiscount(gdiscount)
//            originalToDestinationLineMap.set(refundDetail.orderline.id, newOrderline);
//            refundDetail.destinationOrderUid = destinationOrder.uid;
//        }
//
//        //Add a check too see if the fiscal position exist in the pos
//        if (order.fiscal_position_not_found) {
//            this.showPopup("ErrorPopup", {
//                title: _t("Fiscal Position not found"),
//                body: _t(
//                    "The fiscal position used in the original order is not loaded. Make sure it is loaded by adding it in the pos configuration."
//                ),
//            });
//            return;
//        }
//        destinationOrder.fiscal_position = order.fiscal_position;
//        // Set the partner to the destinationOrder.
//        this.setPartnerToRefundOrder(partner, destinationOrder);
//
//        if (this.pos.get_order().cid !== destinationOrder.cid) {
//            this.pos.set_order(destinationOrder);
//        }
//
//        this.closeTicketScreen();
//    },
//
//
//
//
//
//
//  async approve() {
//    const employee = this.pos.get_cashier();
//    const employeeName = employee.name;
//    const managers = this.pos.employees.filter((obj) => obj.role === 'manager');
//
//    if (managers.length === 0) {
//        this.popup.add(ErrorPopup, {
//            title: _t("No Manager Available"),
//            body: _t(`${employeeName}, there are no managers available for approval.`),
//        });
//        return false;
//    }
//
//    const manager = managers[0];
//    const managerName = manager.name;
//
//    const { confirmed, payload } = await this.popup.add(NumberPopup, {
//        title: _t(`${employeeName}, your order is beyond 14 days. \n Manager ${managerName}'s PIN for approval.`),
//        isPassword: true,
//    });
//
//    if (!confirmed) {
//        return false;
//    }
//
//    try {
//        const pin = manager.pin;
//        if (Sha1.hash(payload) === pin) {
//            console.log("Approval granted.");
//            return true;
//        } else {
//            this.popup.add(ErrorPopup, {
//                title: _t("Manager Restricted Your Discount"),
//                body: _t(`${employeeName}, Manager ${managerName}'s PIN is incorrect.`),
//            });
//            return false;
//        }
//    } catch (error) {
//        if (error instanceof ConnectionLostError) {
//            return Promise.reject(error);
//        } else {
//            throw error;
//        }
//    }
//},
//
//
//
//});