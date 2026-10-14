"""Black-box checks of an already running DataCollectorService."""

import argparse
import configparser
import csv
import io
import json
import os
from pathlib import Path
import socket
import unittest
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / 'config.ini'


def load_settings(config_path=DEFAULT_CONFIG, base_url=None, access_key=None, timeout=10):
    base_url = base_url or os.environ.get('DATACOLLECTOR_URL')
    access_key = access_key or os.environ.get('DATACOLLECTOR_ACCESS_KEY')
    config = configparser.ConfigParser(interpolation=None)
    try:
        if config_path.exists():
            with config_path.open(encoding='utf-8') as ini:
                config.read_file(ini)
        if not access_key:
            access_key = config.get('WEBSERVICE', 'access_key', fallback=None)
        if not base_url:
            port = config.getint('WEBSERVICE', 'Port', fallback=8080)
            if not 1 <= port <= 65535:
                raise ValueError('Invalid port')
            base_url = 'http://localhost:{}'.format(port)
    except (OSError, UnicodeError, configparser.Error, ValueError):
        # Parser exceptions can include source lines containing the secret.
        raise ValueError('Cannot read INI settings; check file permissions, format '
                         'and WEBSERVICE.Port') from None
    if not access_key:
        raise ValueError('Access key required: WEBSERVICE.access_key in INI, '
                         '--access-key or DATACOLLECTOR_ACCESS_KEY')
    try:
        url = urlsplit(base_url)
        valid_url = (url.scheme in ('http', 'https') and url.hostname and not url.username
                     and not url.password and not url.query and not url.fragment)
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError('URL must be an HTTP(S) base URL without credentials, query or fragment')
    if timeout <= 0:
        raise ValueError('Timeout must be positive')
    return base_url.rstrip('/'), access_key, timeout


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect can hide a proxy routing problem or forward the access key.
        return None


class DeploymentChecks(unittest.TestCase):
    base_url = None
    access_key = None
    timeout = 10

    @classmethod
    def setUpClass(cls):
        # IDE/unittest runners import this module without calling main().
        if cls.base_url is None:
            cls.base_url, cls.access_key, cls.timeout = load_settings()
        print('Test records use unique tokens; the service TTL controls their expiration.',
              flush=True)

    def request(self, method, path, data=None, key=None, expected=200):
        headers = {}
        if key is not None:
            headers['access-key'] = key
        body = None
        if data is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            response = build_opener(NoRedirects()).open(req, timeout=self.timeout)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, socket.timeout) as error:
            self.fail('{} {}: connection failed ({})'.format(method, path, error))
        with response:
            status, response_headers, content = response.code, response.headers, response.read()
        self.assertEqual(status, expected, '{} {}: unexpected HTTP status'.format(method, path))
        return response_headers, content

    def assert_json(self, headers, body, expected):
        self.assertEqual(headers.get_content_type(), 'application/json')
        self.assertEqual(json.loads(body), expected)

    def assert_qr(self, headers, body, token=None):
        self.assertEqual(headers.get_content_type(), 'image/png')
        self.assertTrue(body.startswith(b'\x89PNG\r\n\x1a\n'), 'QR response is not PNG')
        self.assertGreater(len(body), 32)
        returned_token = headers.get('Token')
        self.assertIsNotNone(returned_token, 'Missing Token response header')
        if token is None:
            self.assertEqual(str(uuid.UUID(returned_token)), returned_token)
        else:
            self.assertEqual(returned_token, token)
        return returned_token

    def new_token(self):
        return 'deployment-check-' + str(uuid.uuid4())

    def test_download_and_json(self):
        """All download routes, Unicode, extraInfo conversion and JSON retrieval."""
        data = [{'barcode': '000123', 'name': 'Тестовый товар',
                 'extraInfo': [{'info': 'Цена', 'value': '12.50'}]}]
        expected = [{'barcode': '000123', 'name': 'Тестовый товар',
                     'extrainfo': [{'info': 'Цена', 'value': '12.50'}]}]
        explicit_token = self.new_token()
        routes = [('/', None), ('/download', None),
                  ('/download/download', None),
                  ('/' + explicit_token + '/download', explicit_token)]
        for path, supplied_token in routes:
            with self.subTest(path=path):
                headers, body = self.request('POST', path, data, self.access_key)
                token = self.assert_qr(headers, body, supplied_token)
                for suffix in ('', '/json'):
                    headers, body = self.request('GET', '/' + token + suffix)
                    self.assert_json(headers, body, expected)

    def test_upload_and_exports(self):
        """QR allocation, mobile upload, JSON retrieval, CSV and overwriting."""
        headers, body = self.request('GET', '/new/upload', key=self.access_key)
        token = self.assert_qr(headers, body)
        self.request('GET', '/' + token + '/upload', expected=404)
        data = [{'barcode': '000123', 'quantity': 2,
                 'serials': [{'serial': 'ТЕСТ-1', 'quantity': 1}]},
                {'barcode': '000456', 'quantity': 3}]
        expected = [{'barcode': '000123', 'quantity': 2,
                     'serial': [{'serial': 'ТЕСТ-1', 'quantity': 1}]},
                    {'barcode': '000456', 'quantity': 3}]
        headers, body = self.request('POST', '/' + token + '/upload', data)
        self.assertEqual(headers.get('Token'), token)
        self.assertEqual(headers.get_content_type(), 'application/json')
        self.assertEqual(body, b'OK')
        for action in ('json', 'upload'):
            headers, body = self.request('GET', '/' + token + '/' + action)
            self.assert_json(headers, body, expected)
        headers, body = self.request('GET', '/' + token + '/csv')
        self.assertEqual(headers.get_content_type(), 'text/csv')
        self.assertEqual(list(csv.reader(io.StringIO(body.decode('utf-8')))),
                         [['barcode', 'quantity'], ['000123', '2'], ['000456', '3']])
        self.request('POST', '/' + token + '/upload', [])
        headers, body = self.request('GET', '/' + token + '/json')
        self.assert_json(headers, body, [])

    def test_keystat(self):
        headers, body = self.request('GET', '/' + self.new_token() + '/keystat',
                                     key=self.access_key)
        self.assertEqual(headers.get_content_type(), 'application/json')
        stat = json.loads(body)
        # Do not include the secret in assertion output.
        self.assertTrue(stat.get('key') == self.access_key, 'keystat key mismatch')
        self.assertEqual(stat.get('validTo'), '7658-05-17')

    def test_protected_operations(self):
        for key in (None, 'invalid-' + str(uuid.uuid4())):
            with self.subTest(key='missing' if key is None else 'invalid'):
                self.request('GET', '/new/upload', key=key, expected=401)
                token = self.new_token()
                self.request('POST', '/' + token + '/download', [], key, expected=401)
                self.request('GET', '/' + token + '/json', expected=404)

    def test_missing_tokens(self):
        for action in ('json', 'upload', 'csv'):
            with self.subTest(action=action):
                self.request('GET', '/' + self.new_token() + '/' + action, expected=404)

    def test_unknown_actions(self):
        path = '/' + self.new_token() + '/unknown-action'
        self.request('GET', path, expected=404)
        self.request('POST', path, [], self.access_key, expected=404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path,
                        default=DEFAULT_CONFIG,
                        help='INI settings file (default: project config.ini)')
    parser.add_argument('--url', default=os.environ.get('DATACOLLECTOR_URL'),
                        help='Service base URL (or DATACOLLECTOR_URL; default: localhost with INI Port)')
    parser.add_argument('--access-key', default=os.environ.get('DATACOLLECTOR_ACCESS_KEY'),
                        help='Access key (prefer DATACOLLECTOR_ACCESS_KEY to avoid shell history)')
    parser.add_argument('--timeout', type=float, default=10,
                        help='Timeout per HTTP request in seconds (default: 10)')
    args = parser.parse_args()
    try:
        DeploymentChecks.base_url, DeploymentChecks.access_key, DeploymentChecks.timeout = (
            load_settings(args.config, args.url, args.access_key, args.timeout))
    except ValueError as error:
        parser.error(str(error))
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentChecks))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
