from odoo import http
from odoo.addons.web.controllers.database import Database
import markupsafe


class DatabaseProtect(Database):

    def _inject_js(self, response):
        import time
        version = int(time.time())
        injection = f'<script src="/tree_view_advanced_search/static/src/js/db_delete_lock.js?v={version}"></script>'

        # If response is a werkzeug Response object
        if hasattr(response, 'get_data') and hasattr(response, 'set_data'):
            html_content = response.get_data(as_text=True)
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{injection}</body>')
                response.set_data(html_content)
            return response

        # If response is bytes
        if isinstance(response, bytes):
            html_content = response.decode('utf-8')
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{injection}</body>')
            return html_content.encode('utf-8')

        # If response is string or Markup
        if hasattr(markupsafe, 'Markup') and isinstance(response, markupsafe.Markup):
            injection = markupsafe.Markup(injection)

        if '</body>' in response:
            response = response.replace('</body>', f'{injection}</body>')
        return response

    @http.route('/web/database/manager', type='http', auth="none")
    def manager(self, **kw):
        response = super().manager(**kw)
        return self._inject_js(response)

    @http.route('/web/database/selector', type='http', auth="none")
    def selector(self, **kw):
        response = super().selector(**kw)
        return self._inject_js(response)