/** @odoo-module **/
import { Component, useState, useEffect, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { DuplicateLotSelectionPopup } from "@nhcl_pos_sale/app/duplicate_lot_selection_popup/duplicate_lot_selection_popup";
import { CustomButtonPopup } from "@nhcl_pos_sale/app/custom_popup/custom_popup";
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

            // Check if the user scanned/typed a specific Lot Name that is already sold
            const exactLotMatches = await this.orm.call('stock.lot', 'search_read', [
                [['name', '=', formattedValue]],
                ['id', 'name', 'ref', 'rs_price', 'is_under_plan', 'sale_tax_ids', 'product_qty_pos', 'location_id', 'type_product', 'product_id', 'is_used']
            ]);

            if (exactLotMatches && exactLotMatches.length > 0) {
                const exactLot = exactLotMatches[0];
                if (exactLot.is_used && (!exactLot.product_qty_pos || exactLot.product_qty_pos <= 0)) {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Already Sold Lot / Serial Number"),
                        body: _t(`Serial Number '${exactLot.name}' has already been sold and used.`),
                    });
                    return;
                }
            }

            const domain = [
                ['product_qty_pos', '>', 0],
                '|',
                ['name', '=', formattedValue],
                ['ref', '=', formattedValue]
            ];
            // 1. Try to find the lot in the database
            let lots = await this.orm.call('stock.lot', 'search_read', [
                domain,
                ['id', 'name', 'ref', 'rs_price', 'is_under_plan', 'sale_tax_ids', 'product_qty_pos', 'location_id', 'type_product', 'product_id']
            ]);

            let lot = null;

            if (lots && lots.length > 0) {
                // Filter out lots that are ALREADY added to the cart
                const remainingLots = lots.filter(l => !lotNames.includes(l.name));

                if (remainingLots.length > 1) {
                    const distinctProductIds = new Set(remainingLots.map(l => l.product_id ? l.product_id[0] : null).filter(Boolean));
                    const hasNameMatch = remainingLots.some(l => l.name === formattedValue);
                    const hasRefMatch = remainingLots.some(l => l.ref === formattedValue);
                    const isNameAndRefCrossMatch = hasNameMatch && hasRefMatch;

                    if (distinctProductIds.size > 1 || isNameAndRefCrossMatch) {
                        // Open popup if multiple lots match across different product variants or name/ref cross matches
                        const { confirmed, payload: selectedLot } = await this.pos.env.services.popup.add(DuplicateLotSelectionPopup, {
                            title: _t("Select Matching Item / Variant"),
                            formattedValue: formattedValue,
                            lots: remainingLots,
                        });
                        if (!confirmed || !selectedLot) {
                            return;
                        }
                        lot = selectedLot;
                    } else {
                        const matchingNameLots = remainingLots.filter(l => l.name === formattedValue);
                        if (matchingNameLots.length > 1) {
                            this.pos.env.services.popup.add(ErrorPopup, {
                                title: _t("Duplicate Lot Found"),
                                body: _t(`Multiple lots found with lot number '${formattedValue}'.`),
                            });
                            return;
                        } else if (matchingNameLots.length === 1) {
                            lot = matchingNameLots[0];
                        } else {
                            lot = remainingLots[0];
                        }
                    }
                } else if (remainingLots.length === 1) {
                    // Exactly one pending lot remaining: scan it directly without showing popup again
                    lot = remainingLots[0];
                } else if (remainingLots.length === 0) {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Serial Number Duplication Not Allowed"),
                        body: _t(`Serial Number ${formattedValue} already exists in the Order`),
                    });
                    return;
                }
            }

            if (lot) {
                this.pos.stock_lots_by_name[lot.name] = { stockLot: lot };
                if (lot.ref && !this.pos.stock_lots_by_name[lot.ref]) {
                    this.pos.stock_lots_by_name[lot.ref] = { stockLot: lot };
                }
                if (formattedValue && !this.pos.stock_lots_by_name[formattedValue]) {
                    this.pos.stock_lots_by_name[formattedValue] = { stockLot: lot };
                }

                if (lot.product_id && lot.product_id[0]) {
                    const pId = lot.product_id[0];
                    if (!this.pos.stock_lots_by_product_id) {
                        this.pos.stock_lots_by_product_id = {};
                    }
                    if (!this.pos.stock_lots_by_product_id[pId]) {
                        this.pos.stock_lots_by_product_id[pId] = {};
                    }
                    this.pos.stock_lots_by_product_id[pId][lot.name] = { stockLot: lot };
                    if (lot.ref) {
                        this.pos.stock_lots_by_product_id[pId][lot.ref] = { stockLot: lot };
                    }
                }

                if (lot.is_under_plan) {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Under Audit Plan"),
                        body: _t(`Serial Number ${lot.name} is under Audit Plan`),
                    });
                    return;
                }

                if (!lot.sale_tax_ids || lot.sale_tax_ids.length === 0) {
                    this.pos.env.services.popup.add(ErrorPopup, {
                        title: _t("Missing Taxes on Lot/Serial Number"),
                        body: _t(`No taxes are configured for the Lot/Serial Number: ${lot.name}`),
                    });
                    return;
                }
                if (lot.sale_tax_ids && lot.sale_tax_ids.length > 0) {
                    const hasIgst = lot.sale_tax_ids.some(taxId => {
                        const tax = this.pos.taxes_by_id[taxId];
                        return tax && (
                            (tax.tax_group_id && Array.isArray(tax.tax_group_id) && tax.tax_group_id[1].toUpperCase().includes('IGST')) ||
                            (tax.name && tax.name.toUpperCase().includes('IGST'))
                        );
                    });
                    if (hasIgst) {
                        this.pos.env.services.popup.add(ErrorPopup, {
                            title: _t("IGST Tax Error"),
                            body: _t(`Serial Number '${lot.name}' has IGST tax applied.`),
                        });
                        return;
                    }
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

                let product = this.pos.db.get_product_by_id(lot.product_id[0]);
                if (!product) {
                    if (typeof this.pos._addProducts === 'function') {
                        await this.pos._addProducts([lot.product_id[0]], false);
                        product = this.pos.db.get_product_by_id(lot.product_id[0]);
                    }
                }

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

                // Directly add the selected lot product to current order
                if (product) {
                    const codeDetails = {
                        'base_code': lot.name,
                        'code': lot.name,
                        'type': "lot",
                        'value': lot.name,
                    };
                    let options = {};
                    if (typeof product.getAddProductOptions === 'function') {
                        options = await product.getAddProductOptions(codeDetails);
                    } else {
                        options = {
                            pack_lot_lines: [{ lot_name: lot.name }]
                        };
                    }
                    options.price = lot.rs_price;
                    options.merge = false;
                    if (scannedQty !== null) {
                        options.quantity = scannedQty;
                    }

                    let addRes = true;
                    if (product.tracking === 'lot') {
                        const lot_name = lot.name;
                        const existing_line = current_order.orderlines.find(orderline => {
                            return orderline.product.id === product.id &&
                                orderline.pack_lot_lines &&
                                orderline.pack_lot_lines.some(pack => pack.lot_name === lot_name);
                        });
                        if (existing_line) {
                            existing_line.set_quantity(existing_line.get_quantity() + (scannedQty !== null ? scannedQty : 1));
                        } else {
                            addRes = await current_order.add_product(product, options);
                        }
                    } else {
                        addRes = await current_order.add_product(product, options);
                    }

                    if (addRes !== false) {
                        if (typeof current_order._updateRewards === 'function') {
                            current_order._updateRewards();
                        }
                        if (typeof current_order.check_remove_unapplicable_reward_id === 'function') {
                            current_order.check_remove_unapplicable_reward_id();
                        }

                        // Trigger Salesperson selection popup after adding item
                        await this.set_sales_employee();
                    }
                } else {
                    await this.barcodeReader.scan(formattedValue);
                }
            } else {
                // Non-cross match scan / unbranded scan -> fallback to standard barcode processing
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

    async set_sales_employee() {
        const popupService = (this.pos && this.pos.env && this.pos.env.services && this.pos.env.services.popup) || (this.env && this.env.services && this.env.services.popup);
        const order = this.pos.get_order();
        if (!order) {
            return;
        }
        const orderlines = order.get_orderlines();
        let selectedOrderline = order.get_selected_orderline();
        if (!selectedOrderline && orderlines.length > 0) {
            selectedOrderline = orderlines.at(-1);
            if (selectedOrderline) {
                order.select_orderline(selectedOrderline);
            }
        }

        if (!selectedOrderline) {
            console.warn("set_sales_employee: No selected orderline found.");
            return;
        }

        let default_badge = "";
        if (orderlines.length > 1) {
            const prevLine = orderlines.filter((line) => line.cid !== selectedOrderline.cid && !line.is_reward_line).at(-1);
            default_badge = prevLine ? prevLine.badge : "";
        } else if (orderlines.length > 0) {
            default_badge = orderlines[0].badge;
        }
        const { confirmed, payload: inputValue } = await popupService.add(CustomButtonPopup, {
            startingValue: default_badge,
            title: _t("Add SALE PERSON"),
        });

        const value = inputValue || "";
        if (Object.keys(popupService.popups).length === 0) {
            if (value.trim() == "") {
                await popupService.add(ErrorPopup, {
                    title: _t("Sales employee mandatory"),
                    body: _t("Please Enter Sales Person Id."),
                });
                return this.set_sales_employee();
            }
        }

        const emp_yes = await this.orm.call('hr.employee', 'search_read',
            [[['barcode', '=', value.trim()]]],
            { fields: ['id', 'barcode', 'name'], limit: 1 }
        );
        const e = emp_yes.find((emp) => emp.barcode === value.trim());
        if (!e) {
            if (Object.keys(popupService.popups).length === 0) {
                await popupService.add(ErrorPopup, {
                    title: _t("Please Enter Correct Id"),
                    body: _t("Please Try Again"),
                });
                return this.set_sales_employee();
            }
            return false;
        }

        selectedOrderline.set_emp_no(e.name);
        selectedOrderline.set_badge_id(e.barcode);
        selectedOrderline.set_employee_id(e.id);
        if (typeof selectedOrderline.order._updateRewards === 'function') {
            selectedOrderline.order._updateRewards();
        }
        return true;
    }
}