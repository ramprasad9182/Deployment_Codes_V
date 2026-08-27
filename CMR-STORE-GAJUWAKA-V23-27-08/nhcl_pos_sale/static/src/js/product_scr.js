/** @odoo-module */
import { CustomButtonPopup } from "@nhcl_pos_sale/app/custom_popup/custom_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { CustomSearch } from "@nhcl_pos_sale/app/screens/product_screen/custom_search/custom_search";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { MultiSelectionPopup } from "@nhcl_pos_sale/app/multi_selection_popup/multi_selection_popup";
import { ApplicableProgramsInfoPopup } from "@nhcl_pos_sale/app/applicable_programs_info_popup/applicable_programs_info_popup";
import { Packlotline } from "@point_of_sale/app/store/models";
import { CustomEditListPopup } from "@nhcl_pos_sale/app/select_lot_with_qty_popup/select_lot_with_qty_popup";

patch(ProductScreen.prototype, {

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
    },

    async onClickPay() {
        if (this.pos.payment_transition_in_progress) {
            return;
        }
        // Block if customer list, wizard, or details editor is open in the DOM
        if (document.querySelector(".partnerlist-screen, .partner-details, .partner-editor, .partner-details-edit, .partner-list")) {
            return;
        }
        this.pos.payment_transition_in_progress = true;
        try {
            const order = this.currentOrder;
            if (order) {
                // If customer is not set, open the customer selection list automatically
                if (!order.get_partner()) {
                    this.pos.go_to_payment_after_selecting_customer = true;
                    this.pos.payment_transition_in_progress = false;
                    await this.pos.selectPartner();
                    return;
                }
                const totalAmount = typeof order.get_custom_totalwithtax === 'function' ? order.get_custom_totalwithtax() : order.get_total_with_tax();
                if (totalAmount > 199000) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Order Amount Limit Reached"),
                        body: _t("Please reduce the order total to ₹199,000 or less and complete the payment. Move the remaining items to a new order."),
                    });
                    this.pos.payment_transition_in_progress = false;
                    return;
                }
            }
            await super.onClickPay(...arguments);
        } finally {
            this.pos.payment_transition_in_progress = false;
        }
    },

    //  Pranav Start
    _setValue(val) {
        //      Restrict to change anything on amount fix discount line
        const selectedLine = this.currentOrder.get_selected_orderline();
        if (
            selectedLine &&
            selectedLine.is_fix_discount_line
        ) {
            return;
        } else {
            super._setValue(val);
        }
    },
    //    Stop

    async _barcodeProductAction(code) {
        if (this.scanInProgress || Object.keys(this.popup.popups).length !== 0) {
            return;
        }
        this.scanInProgress = true;
        try {
            return await this._barcodeProductActionLocked(code);
        } finally {
            this.scanInProgress = false;
        }
    },

    async _barcodeProductActionLocked(code) {
        let self = this;
        let selectedOrder = this.pos.get_order();
        let barcode = this.env.services.pos.barcode_by_name[code.base_code];
        if (barcode) {
            let products = [];
            if (barcode.product_id) {
                let product = this.env.services.pos.db.get_product_by_id(barcode.product_id[0]);

                if (!product) {
                    const productId = barcode.product_id?.[0];
                    const productName = barcode.product_id?.[1] || "Unknown Product";
                    console.warn("Product missing in POS:", productId, productName);
                    return this.popup.add(ErrorPopup, {
                        title: "Product Not Available in POS",
                        body: `Product: ${productName} with ID: ${productId},
                                This product is not available in POS.
                                Please:
                                - Refresh POS
                                - Check Multi Barcode tab
                                - Contact admin if needed`,
                    });
                }
                const orderlines = await this.currentOrder.orderlines;
                let lotNames = []; // Ensure lotNames is declared

                orderlines.forEach(orderline => {
                    if (orderline.product.tracking == 'serial' && orderline.pack_lot_lines.length > 0) {
                        const packLotLines = orderline.pack_lot_lines;
                        packLotLines.forEach(packLotLine => {
                            if (packLotLine.lot_name) {
                                lotNames.push(packLotLine.lot_name);
                            } else {
                                console.log('packLotLine.lot_name is missing or invalid');
                            }
                        });
                    }
                });

                if (product) {
                    const uniqueLots = [];
                    let first_fifo;
                    let is_merge = false;
                    if (product.tracking == 'serial' || product.tracking == "lot") {
                        if (product.tracking == "lot") {
                            is_merge = true
                        }

                        //                         OLD
                        const domain = [
                            ['ref', '=', barcode.barcode],
                            ['is_used', '=', false],
                            ['name', 'not in', lotNames],
                            ['product_qty_pos', '!=', 0],
                            //                        ['location_id', '=', 8]
                        ];
                        try {
                            const brander_serial_nos = await this.orm.call('stock.lot', 'search_read', [domain, ['id', 'name', 'ref', 'rs_price', "mr_price", "is_under_plan", 'product_qty_pos', 'type_product', 'location_id', 'sale_tax_ids']]);
                            // // NEW
                            // const brander_serial_nos = this.pos.stock_lot.filter(lot => {
                            //     return (
                            //         lot.ref === barcode.barcode &&
                            //         lot.is_used === false &&
                            //         !lotNames.includes(lot.name) &&
                            //         lot.product_qty_pos !== 0
                            //     );
                            // });

                            const seenPrices = new Set();

                            for (const lot of brander_serial_nos) {
                                this.pos.stock_lots_by_name[lot.name] = { stockLot: lot };
                                if (!seenPrices.has(lot.rs_price)) {
                                    seenPrices.add(lot.rs_price);
                                    uniqueLots.push(lot);
                                }
                            }

                            first_fifo = brander_serial_nos[0];
                            if (first_fifo) {
                                if (first_fifo.is_under_plan == true) {
                                    return await this.popup.add(ErrorPopup, {
                                        title: _t("Under Audit Plan"),
                                        body: _t("Serial Number " + `${first_fifo.name}` + " Under Audit Plan"),
                                    });
                                }
                                const lotId = first_fifo.id;
                                const programsWithLot = [];
                                for (const program of this.pos.programs) {
                                    if (program.rules) {
                                        for (const rule of program.rules) {
                                            if (rule.serial_ids && rule.serial_ids.has(lotId)) {
                                                programsWithLot.push(program.name);
                                                break;
                                            }
                                        }
                                    }
                                }
                                if (programsWithLot.length > 1) {
                                    return await this.popup.add(ErrorPopup, {
                                        title: _t("Multiple Loyalty Programs"),
                                        body: _t(`Barcode ${first_fifo.ref} is configured in multiple loyalty programs:\n • ${programsWithLot.join(' • ')}.\nScanning is not allowed to prevent system conflicts.`),
                                    });
                                }
                            }
                        } catch (error) {
                            console.error("Error fetching stock lot:", error);
                        }
                    }

                    if (first_fifo) {
                        const lot_damage_return_location = this.pos.stock_location.filter((l) => l.id === first_fifo.location_id[0] && l.cmr_location_type && ["damage_location", "return_location"].includes(l.cmr_location_type));
                        if (lot_damage_return_location.length > 0) {
                            this.pos.env.services.popup.add(ErrorPopup, {
                                title: _t("Wrong Location Error"),
                                body: _t('This item has on %s location. please move to Main location.\n ' +
                                    'For that please click on Damage-Main/Return-Main button',
                                    lot_damage_return_location[0].name),
                            });
                            return;
                        }

                        // Re-fetch current lot names to avoid race conditions (e.g., rapid scans or keyboard repeat / long presses)
                        // and normalize them (trim and uppercase) for a robust check
                        const freshLotNames = [];
                        for (const line of await this.currentOrder.orderlines) {
                            if (line.product.tracking === 'serial') {
                                for (const p of line.pack_lot_lines) {
                                    if (p.lot_name) {
                                        freshLotNames.push(p.lot_name.trim().toUpperCase());
                                    }
                                }
                            }
                        }
                        const scannedCode = (first_fifo.name || '').trim().toUpperCase();
                        // Block duplicate additions if the serial number is already in the order
                        if (product.tracking === 'serial' && scannedCode && freshLotNames.includes(scannedCode)) {
                            if (Object.keys(this.popup.popups).length === 0) {
                                await this.popup.add(ErrorPopup, {
                                    title: _t("Serial Number Duplication Not Allowed"),
                                    body: _t("Serial Number " + `${first_fifo.name}` + " already exists in the Order"),
                                });
                            }
                            return;
                        }

                        const codeDetails = {
                            'base_code': first_fifo.name,
                            'code': first_fifo.name,
                            'type': "lot",
                            'value': first_fifo.name,
                        };

                        const options = await product.getAddProductOptions(codeDetails);
                        options.price = first_fifo.rs_price;
                        options.merge = false;
                        console.log("123", options);

                        if (code.type === "price") {
                            Object.assign(options, {
                                price: code.value,
                                extras: { price_type: "manual" },
                            });
                        } else if (code.type === "weight" || code.type === "quantity") {
                            Object.assign(options, {
                                quantity: code.value,
                                merge: false,
                            });
                        } else if (code.type === "discount") {
                            Object.assign(options, {
                                discount: code.value,
                                merge: false,
                            });
                        }
                        // if (product.tracking === 'lot' && product.nhcl_product_type == 'unbranded') {
                        if (product.tracking === 'lot') {
                            const lot_name = first_fifo.name;
                            const existing_line = orderlines.find(orderline => {
                                return orderline.product.id === product.id &&
                                    orderline.pack_lot_lines.some(pack => pack.lot_name === lot_name);
                            });

                            if (existing_line) {
                                // Increase the existing line’s quantity by 1 (or whatever increment you prefer)
                                existing_line.set_quantity(existing_line.get_quantity() + 1);
                                this.currentOrder._updateRewards();
                                await this.set_sales_employee();
                                //            await this.applicable_rewards_popup();
                                return; // ✅ stop here, don’t add a new line
                            }
                        }

                        selectedOrder.add_product(product, options);
                        this.currentOrder._updateRewards();
                        this.numberBuffer.reset();

                        if (uniqueLots.length > 1) {
                            const lotList = uniqueLots.map((lot) => {
                                return {
                                    id: lot.id,
                                    item: lot,
                                    label: `MRP ₹${lot.mr_price} - Rsp Price ₹${lot.rs_price}`,
                                    isSelected: false,
                                };
                            });

                            const { confirmed, payload: selectedLot } = await this.popup.add(SelectionPopup, {
                                title: _t("Select Price"),
                                list: lotList,
                            });

                            if (!confirmed || !selectedLot) {
                                return;
                            }

                            const selectedLine = this.currentOrder.get_selected_orderline();
                            const packLotLines = selectedLine.pack_lot_lines;
                            for (const lotLine of packLotLines) {
                                selectedLine.pack_lot_lines.remove(lotLine);
                            }

                            let newPackLotLine;
                            newPackLotLine = new Packlotline({ env: this.env }, { order_line: selectedLine });
                            newPackLotLine.lot_name = selectedLot.name;
                            selectedLine.pack_lot_lines.add(newPackLotLine);
                        }
                        await this.set_sales_employee();
                        //                    await this.applicable_rewards_popup();
                    }

                    // Check any reward is applicable or not.
                    // If applicable then it will apply auto, if not then it will remove the reward
                    selectedOrder.check_remove_unapplicable_reward_id();

                    if (product.tracking != 'serial' && product.tracking != 'lot') {
                        const options = await product.getAddProductOptions(barcode.barcode);
                        if (!options) {
                            return;
                        }

                        // Add the code for different `code.type` values here
                        if (code.type === "price") {
                            Object.assign(options, {
                                price: code.value,
                                extras: { price_type: "manual" },
                            });
                        } else if (code.type === "weight" || code.type === "quantity") {
                            Object.assign(options, {
                                quantity: code.value,
                                merge: false,
                            });
                        } else if (code.type === "discount") {
                            Object.assign(options, {
                                discount: code.value,
                                merge: false,
                            });
                        }

                        selectedOrder.add_product(product, options);
                        this.currentOrder._updateRewards();
                        this.numberBuffer.reset();
                        await this.set_sales_employee();
                        //                    await this.applicable_rewards_popup();
                    }
                } else {
                    return true;
                }
            } else if (barcode.product_tmpl_id) {
                let list = self.env.services.pos.db.search_product_in_category(0, code.base_code);
                if (list.length == 1) {
                    selectedOrder.add_product(list[0], { quantity: 1 });
                    this.currentOrder._updateRewards();
                    await this.set_sales_employee();
                    //                await this.applicable_rewards_popup();
                    return true;
                } else {
                    return false;
                }
            } else {
                return false;
            }
        } else {
            super._barcodeProductAction(code);
        }
    },

    async _barcodeGS1Action(parsed_results) {
        if (this.scanInProgress || Object.keys(this.popup.popups).length !== 0) {
            return;
        }
        this.scanInProgress = true;
        try {
            return await this._barcodeGS1ActionLocked(parsed_results);
        } finally {
            this.scanInProgress = false;
        }
    },

    async _barcodeGS1ActionLocked(parsed_results) {
        const orderlines = await this.currentOrder.orderlines;
        const lotNames = [];

        orderlines.forEach(orderline => {
            if (orderline.product.tracking == 'serial' && orderline.pack_lot_lines.length > 0) {
                const packLotLines = orderline.pack_lot_lines;
                packLotLines.forEach(packLotLine => {
                    lotNames.push(packLotLine.lot_name);
                });
            }
        });

        const { product, lotBarcode, customProductOptions } = await this._parseElementsFromGS1(parsed_results);
        console.log('lotBarcode', lotBarcode);

        const domain = [['name', '=', lotBarcode.code]];
        let unbranded_serial_number = [];
        try {
            unbranded_serial_number = await this.orm.call('stock.lot', 'search_read', [domain, ['id', 'name', 'ref', 'rs_price', 'is_under_plan', 'sale_tax_ids']]);
            // unbranded_serial_number = this.pos.stock_lot.filter(lot => {
            //     return (lot.name === lotBarcode.code);
            // });
            if (unbranded_serial_number && unbranded_serial_number.length > 0) {
                for (const lot of unbranded_serial_number) {
                    this.pos.stock_lots_by_name[lot.name] = { stockLot: lot };
                }
                if (unbranded_serial_number[0].is_under_plan) {
                    return await this.popup.add(ErrorPopup, {
                        title: _t("Under Audit Plan"),
                        body: _t("Serial Number " + `${lotBarcode.code}` + " Under Audit Plan"),
                    });
                }
                const lotId = unbranded_serial_number[0].id;
                const programsWithLot = [];
                for (const program of this.pos.programs) {
                    if (program.rules) {
                        for (const rule of program.rules) {
                            if (rule.serial_ids && rule.serial_ids.has(lotId)) {
                                programsWithLot.push(program.name);
                                break;
                            }
                        }
                    }
                }
                if (programsWithLot.length > 1) {
                    return await this.popup.add(ErrorPopup, {
                        title: _t("Multiple Loyalty Programs"),
                        body: _t(`Barcode ${unbranded_serial_number[0].ref} is configured in multiple loyalty programs:\n • ${programsWithLot.join(' • ')}.\nScanning is not allowed to prevent system conflicts.`),
                    });
                }
            }

        } catch (error) {
            console.error("Error fetching unbranded serial number:", error);
        }

        // Re-fetch current lot names to avoid race conditions (e.g., rapid scans or keyboard repeat / long presses)
        // and normalize them (trim and uppercase) for a robust check
        const freshLotNames = [];
        for (const line of await this.currentOrder.orderlines) {
            if (line.product.tracking === 'serial') {
                for (const p of line.pack_lot_lines) {
                    if (p.lot_name) {
                        freshLotNames.push(p.lot_name.trim().toUpperCase());
                    }
                }
            }
        }
        const scannedCode = (lotBarcode?.code || '').trim().toUpperCase();
        // Block duplicate additions if the serial number is already in the order

        if (scannedCode && freshLotNames.includes(scannedCode)) {
            if (Object.keys(this.popup.popups).length === 0) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Serial Number Duplication Not Allowed"),
                    body: _t("Serial Number " + `${lotBarcode.code}` + " already exists in the Order"),
                });
            }
            return;
        } else {
            if (!product) {
                const productBarcode = parsed_results.find((element) => element.type === "product");
                return this.popup.add(ErrorPopup, { code: productBarcode.base_code });
            }
            const options = await product.getAddProductOptions(lotBarcode);

            options.price = unbranded_serial_number.length > 0 ? unbranded_serial_number[0].rs_price : 0;
            if (product.tracking === 'serial' || product.tracking === 'lot') {
                options.merge = false;
                if (product.tracking === 'serial') {
                    options.quantity = 1;
                }
            }

            //            the validation for the serial unbranded no it most be stepped out of the merging
            if (product.tracking === 'serial' && product.nhcl_product_type === 'unbranded') {
                options.merge = false;
                options.quantity = 1;

                await this.currentOrder.add_product(product, {
                    ...options,
                    ...customProductOptions,
                });
                this.numberBuffer.reset();
                this.currentOrder._updateRewards();
                await this.set_sales_employee();
                //                await this.applicable_rewards_popup();
                return;
            }

            if (product.tracking === 'lot' && product.nhcl_product_type == 'unbranded') {
                const lot_name = unbranded_serial_number.length > 0 ? unbranded_serial_number[0].name : '';
                const existing_line = orderlines.find(orderline => {
                    return orderline.product.id === product.id &&
                        orderline.pack_lot_lines.some(pack => pack.lot_name === lot_name);
                });

                if (existing_line) {
                    // Increase the existing line’s quantity by 1 (or whatever increment you prefer)
                    existing_line.set_quantity(existing_line.get_quantity() + 1);
                    this.numberBuffer.reset();
                    this.currentOrder._updateRewards();
                    await this.set_sales_employee();
                    //            await this.applicable_rewards_popup();
                    return; // ✅ stop here, don’t add a new line
                }
            }

            await this.currentOrder.add_product(product, { ...options, ...customProductOptions });
            this.numberBuffer.reset();

            this.currentOrder._updateRewards();
            await this.set_sales_employee();
            //            await this.applicable_rewards_popup();
        }

        console.log(lotBarcode.code);
    },

    async applicable_rewards_popup() {
        let future_applicable_programs = [];
        const selectedline = this.currentOrder.get_selected_orderline();
        let lot_ids = [];
        if (selectedline && selectedline.pack_lot_lines.length > 0) {
            selectedline.pack_lot_lines.forEach(pack => {
                const stockLot = this.pos.stock_lots_by_name[pack.lot_name];
                if (stockLot) {
                    lot_ids.push(stockLot.stockLot.id);
                }
            });
        }
        for (const program of this.pos.programs) {
            if (this.currentOrder._programIsApplicable(program)) {
                if (program.rules.filter(
                    (rule) => rule.any_product || rule.valid_product_ids.has(selectedline.product.id) && rule.serial_ids.has(lot_ids[0]) && rule
                ).length > 0) {
                    future_applicable_programs.push(program);
                }
            }
        }
        //        for (const fp in future_applicable_programs) {
        //            this.notification.add(
        //                _t('Future Reward: %s found.', future_applicable_programs[fp].name),
        //                7000
        //            );
        //        }

        //        const rewardsList = future_applicable_programs.flatMap(item =>
        //            item.rewards.map(reward => ({
        //                id: reward.id,
        //                label: reward.description,
        //                description: item.name,
        //                item: reward,
        //            }))
        //        );
        const rewardsList = future_applicable_programs.map(item => ({
            id: item.id,
            // label: item.name,
            description: item.name,
            item: item,
        }));
        if (rewardsList.length > 0) {
            const { confirmed, payload: selectedCredits } = await this.popup.add(ApplicableProgramsInfoPopup, {
                info: rewardsList
            });
        }
    },

    async action_move_product_damage_to_main() {
        const { confirmed, payload } = await this.popup.add(CustomEditListPopup, {
            title: _t("Add Lot Serial No./Barcode For Transfer Damage to Main Location"),
            isTransferToMainLoc: true,
        });

        if (!confirmed) {
            return;
        }

        const picking_name = await this.orm.call(
            'stock.picking', // Model
            'transfer_damage_main',        // Method
            [
                payload.newArray
            ],
        );

        const barcodeString = payload.newArray.map(item => item.text).join(', ');
        if (picking_name) {
            await this.env.services.popup.add(ConfirmPopup, {
                title: _t("Transfer Created"),
                body: _t("%(picking_name)s Transfer is created for %(barcode)s.", {
                    "picking_name": picking_name,
                    "barcode": barcodeString,
                }),
            });
        } else {
            await this.env.services.popup.add(ConfirmPopup, {
                title: _t("Transfer Error"),
                body: _t("Transfer is not created for %s.", barcodeString),
            });
        }
    },

    async action_move_product_return_to_main() {
        const { confirmed, payload } = await this.popup.add(CustomEditListPopup, {
            title: _t("Add Lot Serial No./Barcode For Transfer Return to Main Location"),
            isTransferToMainLoc: true,
        });

        if (!confirmed) {
            return;
        }

        const picking_name = await this.orm.call(
            'stock.picking', // Model
            'transfer_return_main',        // Method
            [
                payload.newArray
            ],
        );

        const barcodeString = payload.newArray.map(item => item.text).join(', ');
        if (picking_name) {
            await this.env.services.popup.add(ConfirmPopup, {
                title: _t("Transfer Created"),
                body: _t("%(picking_name)s Transfer is created for %(barcode)s.", {
                    "picking_name": picking_name,
                    "barcode": barcodeString,
                }),
            });
        } else {
            await this.env.services.popup.add(ConfirmPopup, {
                title: _t("Transfer Error"),
                body: _t("Transfer is not created for %s.", barcodeString),
            });
        }
    },

    async updateSelectedOrderline({ buffer, key }) {
        const selectedLine = this.currentOrder.get_selected_orderline();
        if (key === "-") {
            if (selectedLine && selectedLine.eWalletGiftCardProgram) {
                // Do not allow negative quantity or price in a gift card or ewallet orderline.
                // Refunding gift card or ewallet is not supported.
                this.notification.add(
                    _t("You cannot set negative quantity or price to gift card or ewallet."),
                    4000
                );
                return;
            }
        }
        if (
            selectedLine &&
            selectedLine.is_reward_line &&
            !selectedLine.manual_reward &&
            (key === "Backspace" || key === "Delete")
        ) {
            const reward = this.pos.reward_by_id[selectedLine.reward_id];
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Deactivating reward"),
                body: _t(
                    "Are you sure you want to remove %s from this order?\n You will still be able to claim it through the reward button.",
                    reward.description
                ),
                cancelText: _t("No"),
                confirmText: _t("Yes"),
            });
            if (confirmed) {
                if (reward.discount_applicability != 'order') {
                    for (var promodiscline of selectedLine.promodisclines) {
                        if (promodiscline) {
                            var remove_line = this.currentOrder.get_orderlines().find(
                                (line) => line.cid === promodiscline);
                            if (remove_line) {
                                remove_line.promo = 0;
                            }
                        } else {
                            continue;
                        }
                    }
                }
                buffer = null;
            } else {
                // Cancel backspace
                return;
            }
        }
        return super.updateSelectedOrderline({ buffer, key });
    },

    async set_sales_employee() {
        const order = this.pos.get_order();
        const orderlines = order.get_orderlines();
        const selectedOrderline = order.get_selected_orderline();

        if (!selectedOrderline) {
            return;
        }

        let default_badge = ""
        if (orderlines.length > 1) {
            // last scanned product's sale person badge
            const prevLine = orderlines.filter((line) => line.cid !== selectedOrderline.cid && !line.is_reward_line).at(-1);
            default_badge = prevLine ? prevLine.badge : "";
        } else if (orderlines.length > 0) {
            default_badge = orderlines[0].badge;
        }
        const { confirmed, payload: inputValue } = await this.popup.add(CustomButtonPopup, {
            startingValue: default_badge,
            title: _t("Add SALE PERSON"),
        });

        const value = inputValue || ""; // Ensure inputValue is a string
        if (Object.keys(this.popup.popups).length === 0) {
            if (value.trim() == "") {
                await this.popup.add(ErrorPopup, {
                    title: _t("Sales employee mandatory"),
                    body: _t("Please Enter Sales Person Id."),
                });
                return this.set_sales_employee();
            }
        }

        // OLD => Issue: It will take time
        // const emp_yes = await this.orm.call('hr.employee', 'search_read', [[]]);
        const emp_yes = await this.orm.call('hr.employee', 'search_read',
            [[['barcode', '=', value.trim()]]],
            { fields: ['id', 'barcode', 'name'], limit: 1 }
        );
        const e = emp_yes.find((emp) => emp.barcode === value.trim());
        // // NEW
        // const e = this.pos.hr_employee.filter(((emp) => emp.barcode_str === value.trim()));
        // if (!e.length) {
        if (!e) {
            if (Object.keys(this.popup.popups).length === 0) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Please Enter Correct Id"),
                    body: _t("Please Try Again"),
                });
                return this.set_sales_employee();
            }
            return false;
        }

        // OLD
        selectedOrderline.set_emp_no(e.name);
        selectedOrderline.set_badge_id(e.barcode);
        selectedOrderline.set_employee_id(e.id);
        // NEW
        // selectedOrderline.set_emp_no(e[0].name);
        // selectedOrderline.set_badge_id(e[0].barcode_str);
        // selectedOrderline.set_employee_id(e[0].id);
        selectedOrderline.order._updateRewards();
        return true;
    },

    async get_credit_details() {
        if (this._isCreditDetailsLoading || (this.popup && Object.keys(this.popup.popups || {}).length > 0)) {
            return;
        }
        this._isCreditDetailsLoading = true;

        try {
            let partner = this.currentOrder.get_partner();

            if (!partner) {
                await this.pos.selectPartner();
                partner = this.currentOrder.get_partner();
                if (!partner) {
                    return;
                }
            }

            try {
                await Promise.race([
                    this.orm.call(
                        "pos.order",
                        "update_credit_voucher_to_customer",
                        [[]],   // ✅ VERY IMPORTANT (empty recordset)
                        { partner_id: partner.id }
                    ),
                    new Promise((resolve) => setTimeout(resolve, 1500))
                ]);
            } catch (error) {
                console.warn("Credit voucher sync failed or timed out:", error);
            }

            let total_credit_amount = 0.00;
            const credit_details = await this.pos.get_redeem_amount(partner.id);
            const valid_credit_details = (credit_details || []).filter((credit) => Math.round(credit.remaining_amount || 0) >= 1);

            if (valid_credit_details && valid_credit_details.length >= 1) {
                const creditDetailsList = valid_credit_details.map((credit) => {
                    let isSelected = false;
                    const roundedAmount = Math.round(credit.remaining_amount || 0);

                    if (
                        this.currentOrder.credit_ids &&
                        this.currentOrder.credit_ids.includes(credit.id)
                    ) {
                        isSelected = true;
                        total_credit_amount += roundedAmount;
                    }

                    return {
                        id: credit.id,
                        item: {
                            ...credit,
                            remaining_amount: roundedAmount,
                        },
                        label: `VC NO ${credit.voucher_number} - Amount ₹${roundedAmount}`,
                        amount: roundedAmount,
                        isSelected: isSelected,
                    };
                });

                const { confirmed, payload: selectedCredits } = await this.popup.add(MultiSelectionPopup, {
                    title: _t("Select Credit"),
                    list: creditDetailsList,
                    total_credit_amount: Math.round(total_credit_amount),
//                multi: true,
                });

                const normalizedCredits = Array.isArray(selectedCredits) ? selectedCredits : (selectedCredits ? [selectedCredits] : []);

                if (!confirmed) {
                    return;
                } else {
                    if (this.currentOrder.paymentlines) {
                        const credit_methods = this.pos.payment_methods.filter(
                            (method) =>
                                method.is_credit_settlement === true &&
                                this.pos.config.payment_method_ids.includes(method.id)
                        );
                        if (credit_methods.length > 0) {
                            const credit_method = credit_methods[0];
                            const same_paymentlines = this.currentOrder.paymentlines.filter(
                                (paymentline) =>
                                    paymentline.payment_method.id === credit_method.id
                            );
                            if (same_paymentlines.length > 0) {
                                for (const line of same_paymentlines) {
                                    this.currentOrder.remove_paymentline(line);
                                }
                            }
                        }
                    }
                }

                // Always reset order credit state on popup confirmation
                this.currentOrder.credit_note_amount = 0.00;
                this.currentOrder.credit_id = 0;
                this.currentOrder.credit_ids = [];
                this.currentOrder.credit_ids_list = [];
                this.currentOrder.credit_partner = false;
                this.currentOrder.credit_note_amounts = [];

                if (normalizedCredits.length === 0) {
                    return;
                }

//            // Assign selected credit data to current order
//            for (const normalizedCredit of normalizedCredits) {
//                if (this.currentOrder.credit_ids && this.currentOrder.credit_ids.includes(normalizedCredit.id)){
//                    await this.popup.add(ErrorPopup, {
//                        title: _t("Credit Note Already added"),
//                        body: _t("The customer Credit Note Already added in this order."),
//                    });
//                    return
//                }
//            }

                this.currentOrder.credit_note_amount = Math.round(
                    normalizedCredits.reduce((sum, credit) => sum + Math.round(credit.remaining_amount || 0), 0)
                );

                let existing_amt = 0
                for (const line of this.currentOrder.paymentlines) {
                    existing_amt += line.amount
                }
//            const total = this.currentOrder.get_total_with_tax() + this.currentOrder.get_rounding_applied();
                const total = Math.round(this.currentOrder.get_custom_totalwithtax());
                this.currentOrder.credit_note_amount = Math.round(
                    Math.min(total - existing_amt, this.currentOrder.credit_note_amount || 0.00)
                );

                if (this.currentOrder.get_partner() && this.currentOrder.get_partner().wallet_amount !== undefined) {
                    this.currentOrder.get_partner().wallet_amount -= this.currentOrder.credit_note_amount;
                }

                this.currentOrder.credit_id = normalizedCredits[0]['id']

                this.currentOrder.credit_ids = [
//                ...this.currentOrder.credit_ids,
                    ...normalizedCredits.map(credit => credit.id)
                ];
                this.currentOrder.credit_ids_list = normalizedCredits;
                this.currentOrder.credit_partner = partner.id;

//            divide used amounts credit note amounts
                const indexed = normalizedCredits.map((item, index) => ({ ...item, index }));
//            let remain_total = this.currentOrder.get_total_with_tax() + this.currentOrder.get_rounding_applied();
                let remain_total = Math.round(this.currentOrder.get_custom_totalwithtax());
                // sort by smallest remaining_amount
                const sorted = [...indexed].sort((a, b) => a.remaining_amount - b.remaining_amount);
                const used = new Array(normalizedCredits.length).fill(0);
                for (const item of sorted) {
                  if (remain_total <= 0) break;

                  const take = Math.round(Math.min(item.remaining_amount, remain_total));
                  used[item.index] = take;

                  remain_total -= take;
                }
                this.currentOrder.credit_note_amounts = used;
            } else {
                await this.popup.add(ErrorPopup, {
                    title: _t("No Credit Available"),
                    body: _t("This customer has no redeemable credit notes."),
                });
            }
        } finally {
            this._isCreditDetailsLoading = false;
        }
    },

});
