import odoo.http as http
import odoo
from odoo import SUPERUSER_ID
from odoo import _
from odoo import api
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.http import Response
from datetime import datetime, date, timedelta
from threading import current_thread
from odoo.addons.web.controllers.main import Database

import logging
_logger = logging.getLogger(__name__)


class Database(Database):

    # HACK https://github.com/odoo/odoo/issues/24183
    # TODO Remove in v12, and use normal odoo.http.request to get details
    @api.model_cr
    def _register_hook(self):
        """🐒-patch XML-RPC controller to know remote address."""
        original_fn = wsgi_server.application_unproxied

        def _patch(environ, start_response):
            current_thread().environ = environ
            return original_fn(environ, start_response)

        wsgi_server.application_unproxied = _patch

    @http.route('/web/database/manager', type='http', auth="none")
    def manager(self, **kw):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        request._cr = None
        return self._render_template()


    @http.route('/web/database/create', type='http', auth="none", methods=['POST'], csrf=False)
    def create(self, master_pwd, name, lang, password, **post):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            if not re.match(DBNAME_PATTERN, name):
                raise Exception(_('Invalid database name. Only alphanumerical characters, underscore, hyphen and dot are allowed.'))
            # country code could be = "False" which is actually True in python
            country_code = post.get('country_code') or False
            dispatch_rpc('db', 'create_database', [master_pwd, name, bool(post.get('demo')), lang, password, post['login'], country_code])
            request.session.authenticate(name, post['login'], password)
            return http.local_redirect('/web/')
        except Exception as e:
            error = "Database creation error: %s" % (str(e) or repr(e))
        return self._render_template(error=error)

    @http.route('/web/database/duplicate', type='http', auth="none", methods=['POST'], csrf=False)
    def duplicate(self, master_pwd, name, new_name):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            if not re.match(DBNAME_PATTERN, new_name):
                raise Exception(_('Invalid database name. Only alphanumerical characters, underscore, hyphen and dot are allowed.'))
            dispatch_rpc('db', 'duplicate_database', [master_pwd, name, new_name])
            return http.local_redirect('/web/database/manager')
        except Exception as e:
            error = "Database duplication error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/drop', type='http', auth="none", methods=['POST'], csrf=False)
    def drop(self, master_pwd, name):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            dispatch_rpc('db','drop', [master_pwd, name])
            request._cr = None  # dropping a database leads to an unusable cursor
            return http.local_redirect('/web/database/manager')
        except Exception as e:
            error = "Database deletion error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/backup', type='http', auth="none", methods=['POST'], csrf=False)
    def backup(self, master_pwd, name, backup_format = 'zip'):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            odoo.service.db.check_super(master_pwd)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = "%s_%s.%s" % (name, ts, backup_format)
            headers = [
                ('Content-Type', 'application/octet-stream; charset=binary'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            dump_stream = odoo.service.db.dump_db(name, None, backup_format)
            response = werkzeug.wrappers.Response(dump_stream, headers=headers, direct_passthrough=True)
            return response
        except Exception as e:
            _logger.exception('Database.backup')
            error = "Database backup error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)

    @http.route('/web/database/restore', type='http', auth="none", methods=['POST'], csrf=False)
    def restore(self, master_pwd, backup_file, name, copy=False):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            data_file = None
            db.check_super(master_pwd)
            with tempfile.NamedTemporaryFile(delete=False) as data_file:
                backup_file.save(data_file)
            db.restore_db(name, data_file.name, str2bool(copy))
            return http.local_redirect('/web/database/manager')
        except Exception as e:
            error = "Database restore error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)
        finally:
            if data_file:
                os.unlink(data_file.name)

    @http.route('/web/database/change_password', type='http', auth="none", methods=['POST'], csrf=False)
    def change_password(self, master_pwd, master_pwd_new):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.database_manager_whitelist')], limit=1)
        if len(parameters) > 0:
            remote_addr = current_thread().environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in current_thread().environ:
                x_forwarded_for_addr = current_thread().environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            dispatch_rpc('db', 'change_admin_password', [master_pwd, master_pwd_new])
            return http.local_redirect('/web/database/manager')
        except Exception as e:
            error = "Master password update error: %s" % (str(e) or repr(e))
            return self._render_template(error=error)
