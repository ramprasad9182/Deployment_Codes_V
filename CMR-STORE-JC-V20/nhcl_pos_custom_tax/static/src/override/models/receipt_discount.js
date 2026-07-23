/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        let grossSale = 0;
        this.get_orderlines().forEach(line => {
            if (line.is_reward_line) {
                return;
            }
            if (!line.is_fix_discount_line) {
                const price = Number(line.get_unit_price()) || 0;
                const qty = Number(line.get_quantity()) || 0;
                let lot_price = price;
                if (line.pack_lot_lines) {
                    const packLotLines = line.pack_lot_lines;
                    let k;
                    if (typeof packLotLines.forEach === 'function') {
                        packLotLines.forEach((pack) => { k = pack.lot_name; });
                    }
                    const stockLot = this.pos.stock_lots_by_name && this.pos.stock_lots_by_name[k];
                    if (stockLot && stockLot.stockLot && stockLot.stockLot.rs_price > 0) {
                        lot_price = stockLot.stockLot.rs_price;
                    }
                }
                grossSale += (lot_price * qty);
            }
        });

        result.gross_sale = grossSale;
        result.net_sale = result.total_with_tax || this.get_total_with_tax();
        result.badge = this.badge || '';
        result.product_total = this.get_custom_totalwithtax();

        // manual discounts values
        const lines = this.get_orderlines();
        const globalDiscountAmount = lines.reduce(
            (sum, line) => sum + Number(line.gdiscount_amount || 0),
            0
        );
        result.global_discount = globalDiscountAmount;

        result.m_discount = lines
            .filter(line => line.is_fix_discount_line)
            .reduce(
                (sum, line) => sum + Math.abs(Number(line.price || 0)),
                0
            );

        const selectedLineDiscount = lines
        .filter(line =>
            (line.get_discount?.() || line.discount || 0) > 0 &&
            !line.reward_id &&
            !line.discount_reward
        )
        .reduce((sum, line) => {
            const discount = line.get_discount?.() || line.discount || 0;
            return sum + (
                line.get_unit_price() *
                line.get_quantity() *
                discount / 100
            );
        }, 0);
        result.selectedLineDiscount = selectedLineDiscount;

        let promoDiscount = 0;
        result.orderlines = result.orderlines.map((line, index) => {
            const orderLine = lines[index];
            let promo_amount = 0;
            let hsn_code = line.l10n_in_hsn_code || '';
            if (orderLine) {
                if (orderLine.reward_id || orderLine.discount_reward || (orderLine.is_reward_line && !orderLine.is_fix_discount_line)) {
                    if (orderLine.reward_id || orderLine.discount_reward) {
                        const mrp = Number(line.product_mrp || 0);
                        const unitPrice = Number(orderLine.get_unit_price() || 0);
                        const mrpDiff = mrp > unitPrice ? (mrp - unitPrice) * orderLine.get_quantity() : 0;
                        const discAmt = orderLine.get_discount_amount() || 0;
                        const discVal = Number(orderLine.discount_value || 0);
                        promo_amount = Math.max(discAmt, mrpDiff, discVal);
                    } else if (orderLine.is_reward_line && !orderLine.is_fix_discount_line) {
                        promo_amount = Math.abs(orderLine.get_display_price() || 0);
                    }
                    promoDiscount += promo_amount;
                }

                // Fetch HSN from stock lot if present
                if (orderLine.pack_lot_lines && orderLine.pack_lot_lines.length) {
                    for (const lot of orderLine.pack_lot_lines) {
                        const lotName = lot.lot_name;
                        const lotObj = this.pos.stock_lots_by_name && this.pos.stock_lots_by_name[lotName];
                        if (lotObj && lotObj.stockLot && lotObj.stockLot.nhcl_lot_hsn_code) {
                            hsn_code = lotObj.stockLot.nhcl_lot_hsn_code;
                            break;
                        }
                    }
                }
            }
            return {
                ...line,
                reward_id: orderLine ? (orderLine.reward_id || orderLine.discount_reward) : false,
                promo_amount,
                l10n_in_hsn_code: hsn_code,
            };
        });
        result.p_discount = promoDiscount;

        // Payment Line amount and name box
        const paymentLines = this.get_paymentlines().filter((p) => !p.is_change);
        result.paymentlines = paymentLines.map(line => ({
                name: line.name,
                amount: line.amount,
        }));
        result.tender_amount = paymentLines.reduce((sum, line) => sum + line.amount, 0);

        return result;
    },
});