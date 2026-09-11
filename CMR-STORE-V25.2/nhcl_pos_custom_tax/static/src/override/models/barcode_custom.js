/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { BarcodeReader } from "@point_of_sale/app/barcode/barcode_reader_service";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PosStore } from "@point_of_sale/app/store/pos_store";


patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(loadedData);
        // Force Product Unit of Measure decimal precision to 3 decimals
        if (this.dp) {
            this.dp["Product Unit of Measure"] = 3;
        }
        // Force kg / KG UoM rounding to 3 decimals (0.001)
        if (this.units_by_id) {
            for (const unit of Object.values(this.units_by_id)) {
                if (unit && unit.name && (unit.name.toLowerCase() === 'kg' || unit.name.toLowerCase().includes('kg'))) {
                    if (unit.rounding > 0.001) {
                        unit.rounding = 0.001;
                    }
                }
            }
        }
    }
});

patch(BarcodeReader.prototype, {
    async _scan(code) {
        if (code && code.includes('#')) {
            const parts = code.split('#');
            const barcodePart = parts[0];
            const qtyPart = parseFloat(parts[1]);
            if (barcodePart && !isNaN(qtyPart)) {
                const originalParseBarcode = this.parser.parse_barcode;
                this.parser.parse_barcode = (c) => {
                    const parsed = originalParseBarcode.call(this.parser, c);
                    if (parsed) {
                        parsed.scanned_qty = qtyPart;
                    }
                    return parsed;
                };
                let originalFallbackParseBarcode = null;
                if (this.fallbackParser) {
                    originalFallbackParseBarcode = this.fallbackParser.parse_barcode;
                    this.fallbackParser.parse_barcode = (c) => {
                        const parsed = originalFallbackParseBarcode.call(this.fallbackParser, c);
                        if (parsed) {
                            parsed.scanned_qty = qtyPart;
                        }
                        return parsed;
                    };
                }
                try {
                    return await super._scan(barcodePart);
                } finally {
                    this.parser.parse_barcode = originalParseBarcode;
                    if (originalFallbackParseBarcode) {
                        this.fallbackParser.parse_barcode = originalFallbackParseBarcode;
                    }
                }
            }
        }
        return await super._scan(code);
    }
});

patch(ProductScreen.prototype, {
    async _barcodeProductAction(code) {
        if (code && code.scanned_qty !== undefined) {
            this.pos.scanned_qty = code.scanned_qty;
            const scannedQty = code.scanned_qty;
            setTimeout(() => {
                if (this.pos.scanned_qty === scannedQty) {
                    delete this.pos.scanned_qty;
                }
            }, 2000);
        }
        return await super._barcodeProductAction(code);
    },
    async _barcodeGS1Action(parsed_results) {
        if (parsed_results && parsed_results.scanned_qty !== undefined) {
            this.pos.scanned_qty = parsed_results.scanned_qty;
            const scannedQty = parsed_results.scanned_qty;
            setTimeout(() => {
                if (this.pos.scanned_qty === scannedQty) {
                    delete this.pos.scanned_qty;
                }
            }, 2000);
        }
        return await super._barcodeGS1Action(parsed_results);
    }
});
