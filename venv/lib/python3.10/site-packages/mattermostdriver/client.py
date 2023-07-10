import logging

import asyncio
import aiohttp
import async_timeout

from .exceptions import (
    InvalidOrMissingParameters,
    NoAccessTokenProvided,
    NotEnoughPermissions,
    ContentTooLarge,
    FeatureDisabled
)

log = logging.getLogger('mattermostdriver.websocket')
log.setLevel(logging.INFO)


class Client:
    def __init__(self, options):
        self._url = '{scheme:s}://{url:s}:{port:d}{basepath:s}'.format(
            scheme=options['scheme'],
            url=options['url'],
            port=options['port'],
            basepath=options['basepath']
        )
        self._scheme = options['scheme']
        self._basepath = options['basepath']
        self._port = options['port']
        self._verify = options['verify']
        self._options = options
        self._token = ''
        self._cookies = None
        self._userid = ''
        self._username = ''
        self._session = aiohttp.ClientSession()

    @property
    def userid(self):
        """
        :return: The user id of the logged in user
        """
        return self._userid

    @userid.setter
    def userid(self, user_id):
        self._userid = user_id

    @property
    def username(self):
        """
        :return: The username of the logged in user. If none, returns an emtpy string.
        """
        return self._username

    @username.setter
    def username(self, username):
        self._username = username

    @property
    def url(self):
        return self._url

    @property
    def cookies(self):
        """
        :return: The cookie given on login
        """
        return self._cookies

    @cookies.setter
    def cookies(self, cookies):
        self._cookies = cookies

    @property
    def token(self):
        """
        :return: The token for the login
        """
        return self._token

    @token.setter
    def token(self, t):
        self._token = t

    def auth_header(self):
        if self._token == '':
            return {}
        return {"Authorization": "Bearer {token:s}".format(token=self._token)}

    @asyncio.coroutine
    def make_request(self, method, endpoint, options=None, params=None, data=None, files=None, basepath=None):
        kwargs = {}

        if options is not None:
            kwargs['json'] = options
        if params is not None:
            kwargs['params'] = params
        if data is not None and options is None:
            kwargs['data'] = data
        if files is not None and options is None:
            _data = kwargs.get('data', {})
            data = aiohttp.FormData()

            for k, v in files.items():
                data.add_field(k, v, content_type='application/octet-stream')

            for k, v in _data.items():
                data.add_field(k, v)

            kwargs['data'] = data

        if data is None:
            data = {}

        if basepath:
            url = '{scheme:s}://{url:s}:{port:d}{basepath:s}'.format(
                scheme=self._options['scheme'],
                url=self._options['url'],
                port=self._options['port'],
                basepath=basepath
            )
        else:
            url = self.url
        method = method.lower()
        request = self._session.get
        if method == 'post':
            request = self._session.post
        elif method == 'put':
            request = self._session.put
        elif method == 'delete':
            request = self._session.delete

        try:
            with async_timeout.timeout(self._options['timeout']):
                response = yield from request(
                    url + endpoint,
                    headers=self.auth_header(),
                    verify_ssl=self._verify,
                    **kwargs
                )
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            if e.code == 400:
                raise InvalidOrMissingParameters(data['message'])
            elif e.code == 401:
                raise NoAccessTokenProvided(data['message'])
            elif e.code == 403:
                raise NotEnoughPermissions(data['message'])
            elif e.code == 413:
                raise ContentTooLarge(data['message'])
            elif e.code == 501:
                raise FeatureDisabled(data['message'])
            else:
                raise

        return response

    @asyncio.coroutine
    def get(self, endpoint, options=None, params=None):
        response = yield from self.make_request('get', endpoint, options=options, params=params)
        try:
            return (yield from response.json())
        except ValueError:
            return response

    @asyncio.coroutine
    def post(self, endpoint, options=None, params=None, data=None, files=None):
        response = yield from self.make_request('post', endpoint, options=options, params=params, data=data, files=files)
        return (yield from response.json())

    @asyncio.coroutine
    def put(self, endpoint, options=None, params=None, data=None):
        response = yield from self.make_request('put', endpoint, options=options, params=params, data=data)
        return (yield from response.json())

    @asyncio.coroutine
    def delete(self, endpoint, options=None, params=None, data=None):
        response = yield from self.make_request('delete', endpoint, options=options, params=params, data=data)
        return (yield from response.json())
