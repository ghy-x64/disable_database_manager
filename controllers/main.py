import ast
import base64
import csv
import functools
import glob
import itertools
import jinja2
import logging
import operator
import datetime
import hashlib
import os
import re
import simplejson
import sys
import time
import urllib2
import zlib
from xml.etree import ElementTree
from cStringIO import StringIO

import babel.messages.pofile
import werkzeug.utils
import werkzeug.wrappers
try:
    import xlwt
except ImportError:
    xlwt = None

import openerp
import openerp.modules.registry
from openerp.addons.base.ir.ir_qweb import AssetsBundle, QWebTemplateNotFound
from openerp.modules import get_module_resource
from openerp.tools import topological_sort
from openerp.tools.translate import _
from openerp.tools import ustr
from openerp import http
from openerp.http import Response

from openerp.http import request, serialize_exception as _serialize_exception
from openerp.addons.web.controllers.main import Database, env, module_boot

import logging
_logger = logging.getLogger(__name__)

class Database(Database):

    @http.route('/web/database/manager', type='http', auth="none")
    def manager(self, **kw):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        # TODO: migrate the webclient's database manager to server side views
        request.session.logout()
        return env.get_template("database_manager.html").render({
            'modules': simplejson.dumps(module_boot()),
        })

    @http.route('/web/database/create', type='json', auth="none")
    def create(self, fields):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        params = dict(map(operator.itemgetter('name', 'value'), fields))
        db_created = request.session.proxy("db").create_database(
            params['super_admin_pwd'],
            params['db_name'],
            bool(params.get('demo_data')),
            params['db_lang'],
            params['create_admin_pwd'])
        if db_created:
            request.session.authenticate(params['db_name'], 'admin', params['create_admin_pwd'])
        return db_created

    @http.route('/web/database/duplicate', type='json', auth="none")
    def duplicate(self, fields):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        params = dict(map(operator.itemgetter('name', 'value'), fields))
        duplicate_attrs = (
            params['super_admin_pwd'],
            params['db_original_name'],
            params['db_name'],
        )

        return request.session.proxy("db").duplicate_database(*duplicate_attrs)


    @http.route('/web/database/drop', type='json', auth="none")
    def drop(self, fields):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        password, db = operator.itemgetter(
            'drop_pwd', 'drop_db')(
                dict(map(operator.itemgetter('name', 'value'), fields)))

        try:
            if request.session.proxy("db").drop(password, db):
                return True
            else:
                return False
        except openerp.exceptions.AccessDenied:
            return {'error': 'AccessDenied', 'title': 'Drop Database'}
        except Exception:
            return {'error': _('Could not drop database !'), 'title': _('Drop Database')}

    @http.route('/web/database/backup', type='http', auth="none")
    def backup(self, backup_db, backup_pwd, token, backup_format='zip'):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            openerp.service.security.check_super(backup_pwd)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = "%s_%s.%s" % (backup_db, ts, backup_format)
            headers = [
                ('Content-Type', 'application/octet-stream; charset=binary'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            dump_stream = openerp.service.db.dump_db(backup_db, None, backup_format)
            response = werkzeug.wrappers.Response(dump_stream, headers=headers, direct_passthrough=True)
            response.set_cookie('fileToken', token)
            return response
        except Exception, e:
            _logger.exception('Database.backup')
            return simplejson.dumps([[],[{'error': openerp.tools.ustr(e), 'title': _('Backup Database')}]])

    @http.route('/web/database/restore', type='http', auth="none")
    def restore(self, db_file, restore_pwd, new_db, mode):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        try:
            copy = mode == 'copy'
            data = base64.b64encode(db_file.read())
            request.session.proxy("db").restore(restore_pwd, new_db, data, copy)
            return ''
        except openerp.exceptions.AccessDenied, e:
            raise Exception("AccessDenied")

    @http.route('/web/database/change_password', type='json', auth="none")
    def change_password(self, fields):
        parameters = request.env['ir.config_parameter'].sudo().search([('key','=','disable_database_manager.customized_sale_module')], limit=1)
        if len(parameters) > 0:
            remote_addr = request.httprequest.environ["REMOTE_ADDR"]
            if 'HTTP_X_FORWARDED_FOR' in request.httprequest.environ:
                x_forwarded_for_addr = request.httprequest.environ["HTTP_X_FORWARDED_FOR"]
                if x_forwarded_for_addr:
                    remote_addr = x_forwarded_for_addr
            _logger.info('remote_addr : ' + str(remote_addr))
            if remote_addr not in parameters.value:
                _logger.info('unauthorized remote_addr : ' + str(remote_addr))
                return Response("Not authorized", status=400)
        old_password, new_password = operator.itemgetter(
            'old_pwd', 'new_pwd')(
                dict(map(operator.itemgetter('name', 'value'), fields)))
        try:
            return request.session.proxy("db").change_admin_password(old_password, new_password)
        except openerp.exceptions.AccessDenied:
            return {'error': 'AccessDenied', 'title': _('Change Password')}
        except Exception:
            return {'error': _('Error, password not changed !'), 'title': _('Change Password')}