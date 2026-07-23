/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { jsonrpc } from "@web/core/network/rpc_service";
import { EditListPopup } from "@point_of_sale/app/store/select_lot_popup/select_lot_popup";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { PosBus } from "@point_of_sale/app/bus/pos_bus_service";
/**
 * EditListPopup Override
 *
 * This module overrides the EditListPopup component in the Point of Sale (POS) module
 * to add custom behavior for serial number validation.
 */
patch(EditListPopup.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
    },
    /**
     * On confirming from the popup after adding lots/ serial numbers,
     * the values are passed to the function validate_lots() for the
     * validation. The corresponding error messages will be displayed
     * on the popup if the lot is invalid or duplicated, or there is
     * no insufficient stock.
     */
    async confirm() {
        console.log("Entered confirm() function...");
        if (this.props.isTransferToMainLoc) {
            return super.confirm();
        }

        if (this.props.title == "Lot/Serial Number(s) Required") {
            console.log("Serial Number popup detected");

            const lot_string = this.state.array;
            console.log("Raw lot_string:", lot_string);

            const lot_names = lot_string
                .filter((l) => l.text !== "")
                .map((l) => l.text);
            console.log("Extracted Lot Names:", lot_names);

            if (lot_names.length === 0) {
                console.warn("No Serial Number entered!");
                this.notification.add(_t("Please Enter a Serial Number."), {
                    type: "danger",
                });
                return false;
            }

            let undef_serial_ids = [];
            let wrong_product_serials = [];
            let valid_serials = [];

            for (let eachItem of lot_names) {
                let lot = this.pos.stock_lots_by_name[eachItem];
                if (lot) {
                    console.log("Found Serial:", eachItem, lot);
                    const product = this.pos.db.get_product_by_id(
                        lot.stockLot.product_id[0]
                    );

                    if (lot.stockLot.product_id && lot.stockLot.product_id[0]) {
                        if (product.display_name === this.props.name) {
                            valid_serials.push(eachItem);
                        } else {
                            wrong_product_serials.push(eachItem);
                        }
                    } else {
                        console.warn("Lot has no product_id:", lot);
                        undef_serial_ids.push(eachItem);
                    }
                } else {
                const inputValue = eachItem.trim();
                    if (inputValue.toLowerCase().startsWith('r')) {
                        const formattedValue = 'R' + inputValue.slice(1);
                        const product = this.pos.barcode_by_name[formattedValue];
                        if (product) {
                            const lot = this.pos.stock_lots_by_product_id[product.product_id[0]];
                            if (lot) {
                                const [firstKey, firstValue] = Object.entries(lot).find(
                                  ([key, value]) => value.stockLot?.ref === formattedValue && value.stockLot?.product_qty_pos > 0
                                );

                                if (firstValue.stockLot.product_id && firstValue.stockLot.product_id[0]) {
                                    const product = this.pos.db.get_product_by_id(
                                        firstValue.stockLot.product_id[0]
                                    );
                                    if (product.display_name === this.props.name) {
                                        if (firstValue.stockLot.type_product === 'un_brand') {
                                            this.popup.add(ErrorPopup, {
                                                title: _t("Reward Not Allowed"),
                                                body: _t("Barcode is allow only for Branded product"),
                                            });
                                            return false;
                                        }
                                        valid_serials.push(firstKey);
                                        this.state.array.filter((l) => l.text === eachItem)[0].text = firstKey;
                                    } else {
                                        wrong_product_serials.push(eachItem);
                                    }
                                } else {
                                    console.warn("Lot has no product_id:", lot);
                                    undef_serial_ids.push(eachItem);
                                }
                            } else {
                                undef_serial_ids.push(eachItem);
                            }
                        } else {
                            undef_serial_ids.push(eachItem);
                        }
                    } else {
                        let product = this.pos.db.get_product_by_barcode(inputValue);
                        let product_id = product?.id;
                        let lot = false;
                        if (!product) {
                           product = this.pos.barcode_by_name[inputValue];
                           product_id = product.product_id[0];
                           lot = this.pos.stock_lots_by_product_id[product_id];
                        } else {
                            lot = this.pos.stock_lots_by_product_id[product_id][0];
                        }
                        if (product) {
                            // const lot = this.pos.stock_lots_by_product_id[product_id][0];
                            if (lot) {
                                const [firstKey, firstValue] = Object.entries(lot).find(
                                  ([key, value]) => value.stockLot?.ref === inputValue && value.stockLot?.product_qty_pos > 0
                                );

                                if (firstValue.stockLot.product_id && firstValue.stockLot.product_id[0]) {
                                    const product = this.pos.db.get_product_by_id(
                                        firstValue.stockLot.product_id[0]
                                    );
                                    if (product.display_name === this.props.name) {
                                        if (firstValue.stockLot.type_product === 'un_brand') {
                                            this.popup.add(ErrorPopup, {
                                                title: _t("Reward Not Allowed"),
                                                body: _t("Barcode is allow only for Branded product"),
                                            });
                                            return false;
                                        }
                                        valid_serials.push(firstKey);
                                        this.state.array.filter((l) => l.text === eachItem)[0].text = firstKey;
                                    } else {
                                        wrong_product_serials.push(eachItem);
                                    }
                                } else {
                                    console.warn("Lot has no product_id:", lot);
                                    undef_serial_ids.push(eachItem);
                                }
                            } else {
                                undef_serial_ids.push(eachItem);
                            }
                        } else {
                            undef_serial_ids.push(eachItem);
                        }
                    }

                    if (!inputValue) {
                        console.error(eachItem, " does NOT exist in system");
                        undef_serial_ids.push(eachItem);
                    }
                }
            }

            // ✅ Final check after loop
            console.log(
                "Summary -> Valid Serials:",
                valid_serials,
                "Invalid Serials:",
                undef_serial_ids,
                "Wrong Product Serials:",
                wrong_product_serials
            );

            if (
                undef_serial_ids.length === 0 &&
                wrong_product_serials.length === 0
            ) {
                console.log("All serials valid. Closing popup.");
                this.props.close({
                    confirmed: true,
                    payload: this.getPayload(),
                });
            } else {
                console.error(
                    "Invalid/Incorrect Serials Found. Showing error popup..."
                );
                this.popup.add(ErrorPopup, {
                    title: _t("Invalid Lot/ Serial Number"),
                    body: _t(
                        "Invalid Serials: " +
                            undef_serial_ids.join(", ") +
                            "\nWrong Product Serials: " +
                            wrong_product_serials.join(", ")
                    ),
                });
                return false;
            }
        } else {
            console.log("Not a Serial Number popup, skipping validation.");
            return true;
        }
    },
});
