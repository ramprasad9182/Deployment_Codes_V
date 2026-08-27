from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from werkzeug.utils import redirect as wz_redirect


# class AccountPostController(http.Controller):
#     @http.route('/api/account.move/call_action', type='json', auth='public', methods=['POST'], csrf=False)
#     def call_action_post_button(self, move_id):
#         move = request.env['account.move'].sudo().browse(move_id)
#
#         if not move.exists():
#             return {'status': 'error', 'message': 'Account move record not found'}
#
#         try:
#             # Call the button action function (replace 'action_post' with your button's method name)
#             move.action_post()
#             return {'status': 'success', 'message': 'Button action executed successfully'}
#         except Exception as e:
#             return {'status': 'error', 'message': str(e)}


class MBQLoginRedirect(Home):
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, **kw):
        response = super().web_login(**kw)
        # after successful login
        if request.session.uid:
            user = request.env.user
            redirect_url = kw.get('redirect')
            if user.has_group(
                    'nhcl_store_to_ho_transactions.group_mbq_notification'
            ) and not redirect_url:
                action = request.env.ref(
                    'nhcl_store_to_ho_transactions.division_view_action',
                    raise_if_not_found=False
                )
                menu = request.env.ref(
                    'nhcl_store_to_ho_transactions.division_view_menu',
                    raise_if_not_found=False
                )
                if action:
                    return wz_redirect(
                        f"/web#action={action.id}&menu_id={menu.id}"
                    )
        return response