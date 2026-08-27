/** @odoo-module **/
import { Component, useState, useEffect, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";


export class CustomSearch extends Component {
    static template = "nhcl_pos_sale.CustomSearch";
    setup() {
        this.pos = usePos();
        this.ui = useState(useService("ui"));
        this.barcodeReader = useService("barcode_reader");
        this.orm = useService("orm");
        this.numberBuffer = useService("number_buffer");

        const handleWindowInteraction = () => {
            setTimeout(() => {
                this._focusInput();
            }, 150);
        };

        setTimeout(() => {
            this._focusInput();
        }, 300);

        onMounted(() => {
            window.addEventListener("click", handleWindowInteraction);
            window.addEventListener("keyup", handleWindowInteraction);
            this._focusInput();
            this._focusInterval = setInterval(() => {
                this._focusInput();
            }, 800);
        });

        onWillUnmount(() => {
            window.removeEventListener("click", handleWindowInteraction);
            window.removeEventListener("keyup", handleWindowInteraction);
            clearInterval(this._focusInterval);
        });
    }

    _focusInput() {
        const popup = document.querySelector(
            ".modal-dialog, .popup, .o-dialog-container, .modal"
        );
        if (popup || (this.ui && this.ui.activeElement !== document)) {
            return;
        }
        const input = document.querySelector(".custom-search input");
        if (!input) {
            return;
        }
        const activeEl = document.activeElement;
        if (activeEl && activeEl !== input) {
            const isOtherInput = activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable;
            if (isOtherInput) {
                return;
            }
        }
        if (activeEl !== input) {
            input.focus();
        }
    }

    async handleKeyDown(event) {
        if (event.key === 'Backspace' || event.key === 'Delete') {
            const inputValue = event.target.value;
            if (!inputValue) {
                event.preventDefault();
                event.stopPropagation();
                if (this.numberBuffer) {
                    this.numberBuffer.sendKey("Backspace");
                }
                return;
            }
        }
        if (event.key !== 'Enter') {
            return;
        }
        event.preventDefault();
        this.showLoadingIndicator = true;
        try {
            let inputValue = event.target.value.trim();
            if (!inputValue) {
                return;
            }

            let scannedQty = null;
            if (inputValue.includes('#')) {
                const parts = inputValue.split('#');
                inputValue = parts[0].trim();
                const qtyVal = parseFloat(parts[1]);
                if (!isNaN(qtyVal)) {
                    scannedQty = qtyVal;
                    this.pos.scanned_qty = scannedQty;
                    // Auto-cleanup after 2 seconds in case scan fails/cancelled
                    setTimeout(() => {
                        if (this.pos.scanned_qty === scannedQty) {
                            delete this.pos.scanned_qty;
                        }
                    }, 2000);
                }
            }

            const current_order = this.pos.get_order();
            const orderlines = current_order.orderlines;
            const lotNames = [];

            orderlines.forEach(orderline => {
                if (orderline.product.tracking === 'serial' && orderline.pack_lot_lines.length > 0) {
                    const packLotLines = orderline.pack_lot_lines;
                    packLotLines.forEach(packLotLine => {
                        lotNames.push(packLotLine.lot_name);
                    });
                }
            });

            // const hasUnderscore = inputValue.includes('_');
            const startsWithR = inputValue.toLowerCase().startsWith('r');

            // Check if the input is a long number (e.g., 10 or more digits)
            // which typically represents a serial/lot number instead of a standard product code
            // const isLongNumericLot = /^\d+$/.test(inputValue) && inputValue.length >= 10;

            // If it matches any of our custom Lot identifier formats, route through the DB lookup
            // if (startsWithR || hasUnderscore || isLongNumericLot) {
                let formattedValue = inputValue;
                if (startsWithR) {
                    formattedValue = 'R' + inputValue.slice(1);
                }

                // Check for duplicate lot records and branded product lot name scans strictly by lot name
                const lotsByName = await this.orm.call('stock.lot', 'search_read', [
                    [['name', '=', formattedValue], ['product_qty_pos', '>', 0]],
                    ['id', 'name', 'type_product']
                ], { limit: 2 });

                if (lotsByName && lotsByName.length > 1) {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Duplicate Lot Found"),
                        body: _t("Multiple lots found with lot number '%s'. Duplicate lot scanning is not allowed.", formattedValue),
                    });
                    return;
                }

                if (lotsByName && lotsByName.length === 1 && lotsByName[0].type_product === 'brand') {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Entry Not Allowed"),
                        body: _t("Branded product scan with barcode only."),
                    });
                    return;
                }

                const domain = [[
                    ['product_qty_pos', '>', 0],
                    ['is_used', '=', false],
                    ['name', 'not in', lotNames],
                    '|',
                    ['name', '=', formattedValue],
                    ['ref', '=', formattedValue]
                ]];
                // 1. Try to find the lot in the database
                let lots = await this.orm.call('stock.lot', 'search_read', [domain[0], ['id', 'name', 'ref', 'rs_price', 'is_under_plan', 'sale_tax_ids', 'product_qty_pos', 'location_id', 'type_product', 'product_id']], { limit: 1 });

                let lot = lots && lots[0];

                if (lot) {
                    this.pos.stock_lots_by_name[lot.name] = { stockLot: lot };
                    if (!lot.sale_tax_ids || lot.sale_tax_ids.length === 0) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("Missing Taxes on Lot/Serial Number"),
                            body: _t(`No taxes are configured for the Lot/Serial Number: ${lot.name}`),
                        });
                        return;
                    }
                    const availableQty = lot.product_qty_pos || 0;
                    const existingLine = current_order.orderlines.find(line =>
                        line.pack_lot_lines && line.pack_lot_lines.some(pack => pack.lot_name === lot.name)
                    );
                    const currentCartQty = existingLine ? existingLine.get_quantity() : 0;
                    const requestedQty = scannedQty !== null ? scannedQty : 1;
                    if (currentCartQty + requestedQty > availableQty) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("Quantity Exceeded"),
                            body: _t(
                                "Cannot add %s quantity for lot %s. Available stock: %s, Current cart: %s.",
                                requestedQty, lot.name, availableQty, currentCartQty
                            ),
                        });
                        return;
                    }

                    const products = await this.orm.call(
                        'product.product',
                        'search_read',
                        [[['id', '=', lot.product_id[0]]]],
                        {
                            fields: ['id', 'barcode', 'qty_available', 'nhcl_product_type'],
                            limit: 1
                        }
                    );
                    const product = products && products[0];

                    if (!lot.product_qty_pos || lot.product_qty_pos <= 0) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: "No Stock Available",
                            body: "This item has no on-hand quantity.",
                        });
                        return;
                    }

                    const lot_damage_return_location = this.pos.stock_location.filter(
                        (l) =>
                            l.id === lot.location_id[0] &&
                            l.cmr_location_type &&
                            ["damage_location", "return_location"].includes(l.cmr_location_type)
                    );
                    if (lot_damage_return_location.length > 0) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("Wrong Location Error"),
                            body: _t(
                                'This item has on %s location. please move to Main location.\n For that please click on Damage-Main/Return-Main button',
                                lot_damage_return_location[0].name
                            ),
                        });
                        return;
                    }
                    if (lot.type_product === 'brand' && lot.name === formattedValue) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("Entry Not Allowed"),
                            body: _t("Branded product scan with barcode only."),
                        });
                        return;
                    }

                    // Route safely into the Odoo scan parser using GS1 composition rules
                    if (product && product.barcode) {
                        await this.barcodeReader.scan(`01${product.barcode}21${lot.name}`);
                    } else {
                        await this.barcodeReader.scan(formattedValue);
                    }
                } else {
                    // Lot wasn't found in system, fallback to regular scan processing
                    await this.barcodeReader.scan(formattedValue);
                }
            // } else {
            //     // Standard product barcodes go straight here
            //     this.barcodeReader.scan(inputValue);
            // }
        } catch (error) {
            console.error('Error processing input:', error);
        } finally {
            this.showLoadingIndicator = false;
            this.pos.searchProductByCode = "";
            event.target.value = "";
            this._focusInput();
        }
    }
}