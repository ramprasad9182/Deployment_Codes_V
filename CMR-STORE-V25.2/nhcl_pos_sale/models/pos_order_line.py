from odoo.addons.pos_loyalty.models.pos_order_line import PosOrderLine


# 1. Save a reference to the original method if you still want to call it
# original_order_line_fields = PosOrderLine._order_line_fields

# 2. Define your completely new custom function
def custom_order_line_fields(self, line, session_id=None):
    # Call the super of 'pos.order.line' directly, completely skipping the pos_loyalty version
    res = super(PosOrderLine, self)._order_line_fields(line, session_id)

    if 'coupon_id' in res[2] and res[2]['coupon_id'] and res[2]['coupon_id'] < 1:
        res[2].pop('coupon_id')

    return res


# 3. Replace the original method with your custom one
PosOrderLine._order_line_fields = custom_order_line_fields
