import odoo
import logging
from odoo import http,fields
from odoo.http import request
from odoo.addons.web.controllers.home import ensure_db,Home
from odoo.tools import pycompat
from odoo.tools import config
from odoo.tools.translate import _
from datetime import date

import odoo.exceptions
from werkzeug.utils import redirect

_logger = logging.getLogger(__name__)


class WebControllerCustom(Home):

    @http.route('/web/login', type='http', auth='none', website=True)
    def web_login(self, redirect=None, **kw):
        # Your debug code here
        print("🔍 Custom login route triggered")
        print("Redirect target:", redirect)
        print("Post data:", kw)
        # Call the original method (optional)
        response = super(WebControllerCustom, self).web_login(redirect=redirect, **kw)

        request.params['login_success'] = False
        ensure_db()

        if request.httprequest.method == 'GET' and redirect and request.session.uid:
            return request.redirect(redirect)

        if request.env.uid is None:
            if request.session.uid is None:
                request.env["ir.http"]._auth_method_public()
            else:
                request.update_env(user=request.session.uid)

        values = {k: v for k, v in request.params.items()}
        try:
            values['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values['databases'] = None

        if request.httprequest.method == 'POST':
            login = request.params.get('login')
            password = request.params.get('password')
            db = request.session.db
            # user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            # print("****************************", user)
            # if user:
            #     if user.expiry_date and user.expiry_date < fields.Date.today():
            #         values['error'] = _("Your account has expired. Please contact the administrator.")
            #         return request.render('web.login', values)


            try:
                uid = request.session.authenticate(db, login, password)
                print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&",uid)

                user = request.env['res.users'].sudo().browse(uid)
                if user.expiry_date and user.expiry_date < fields.Date.today():
                    _logger.warning(f"Login blocked: User '{user.login}' account expired on {user.expiry_date}")
                    request.session.logout()  # Optional: forcibly log out if already authenticated
                    values['error'] = _("Your account has expired. Please contact the administrator.")
                    return request.render('web.login', values)

                request.params['login_success'] = True
                return request.redirect(self._login_redirect(uid, redirect=redirect))
            except odoo.exceptions.AccessDenied as e:
                values['error'] = _("Wrong login/password")

        else:
            if 'error' in request.params and request.params.get('error') == 'access':
                values['error'] = _('Only employees can access this database. Please contact the administrator.')

        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')

        if not odoo.tools.config['list_db']:
            values['disable_database_manager'] = True

        response = request.render('web.login', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response


