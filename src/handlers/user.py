import time
import uuid
import base64
import hashlib
import logging
import collections

import oauth2

logger = logging.getLogger(__name__)
Account = collections.namedtuple('Account', ('id', 'login', 'email', 'shared_secret', 'consumer_key'))
OAuthAccount = collections.namedtuple('OAuthAccount', ('secret', 'key'))
oauth_server = oauth2.Server(signature_methods={
            'HMAC-SHA1': oauth2.SignatureMethod_HMAC_SHA1()
        })

def convert_account_to_oauth_account(account):
    # oauth lib wants an object with a "key" attribute
    # and a "secret" attribute; so we'll give it that
    return OAuthAccount(
        secret = account.shared_secret,
        key = account.consumer_key
    )


# get_* takes a conn and does a query
# select_* takes a cursor and does a query,
# allowing for multiple queries w/in a transaction

def select_account_by_id(cursor, user_id):
    q = """SELECT `id`, `login`, `email`, `shared_secret`, `consumer_key`
    FROM `users`
    WHERE `id` = ?
    AND `status` = 'active'
    """
    cursor.execute(q, (user_id,))
    existing_account = cursor.fetchone()
    if not existing_account:
        return None
    return Account(**existing_account)

def get_account_by_id(conn, user_id):
    assert user_id is not None
    with conn.cursor() as cursor:
        return select_account_by_id(cursor, user_id)

def select_account_by_login(cursor, login, service):
    assert login
    q = """SELECT `id`, `login`, `email`, `shared_secret`, `consumer_key`
    FROM `users`
    WHERE `login` = ?
    AND `service` = ?
    AND`status` = 'active'
    """
    cursor.execute(q, (login, service))
    existing_account = cursor.fetchone()
    if not existing_account:
        return None
    return Account(**existing_account)

def get_account_by_login(conn, login, service):
    with conn.cursor() as cursor:
        return select_account_by_login(cursor, login, service)

def insert_account(cursor, login, service, email):
    q = """INSERT INTO users
    (`login`, `service`, `email`, `status`, `last_login`, `date_joined`, `shared_secret`, `consumer_key`)
    VALUES (?,?,?,?,?,?,?,?)
    """
    now = int(time.time())
    shared_secret = base64.encodestring(uuid.uuid4().bytes)[:-3]
    consumer_key = hashlib.md5(base64.encodestring(uuid.uuid4().bytes)[:-3]).hexdigest()
    status = 'active'
    cursor.execute(q, (login, service, email, status, now, now, shared_secret, consumer_key))
    user_id = cursor.lastrowid
    existing_account = {'id': user_id,
                        'login': login,
                        'email': email,
                        'shared_secret':shared_secret,
                        'consumer_key':consumer_key}
    return Account(**existing_account)

def create_account(conn, login, service, email):
    with conn.cursor() as cursor:
        return insert_account(cursor, login, service, email)

def update_reset_account_credentials(cursor, account):
    assert isinstance(account, Account)
    q = """UPDATE users
    SET `shared_secret` = ?, `consumer_key` = ?
    WHERE `id` = ?
    """
    shared_secret = base64.encodestring(uuid.uuid4().bytes)[:-3]
    consumer_key = hashlib.md5(base64.encodestring(uuid.uuid4().bytes)[:-3]).hexdigest()
    cursor.execute(q, (shared_secret, consumer_key))
    return account._replace({'shared_secret':shared_secret, 'consumer_key':consumer_key})

def reset_account_credentials(conn, account):
    with conn.cursor() as cursor:
        return update_reset_account_credentials(cursor, account)

def delete_account(cursor, account):
    q = """UPDATE users
    SET `status` = 'deleted'
    WHERE `id` = ?
    """
    cursor.execute(q, (account.id))

def remove_account(conn, account):
    with conn.cursor() as cursor:
        return delete_account(cursor, account)


# def create_or_get_account(conn, login, service, email):
#     """
#         within a single transaction, see if the account exists, and if not, create it
#     """
#     with conn.cursor() as cursor:
#         existing = get_account_by_login(cursor, login, service)
#         if not existing:
#             existing = create_account(cursor, login, service, email)
#     # implicit commit as cursor contextmanager is released
#     return existing


class OauthError(Exception):
    def __init__(self, http_error_msg):
        Exception.__init__(self, "API Error")
        self.msg = http_error_msg

class OauthInvalidParamError(OauthError):
    pass

class OauthUnauthorized(OauthError):
    pass

required_oauth_params = (
    'oauth_body_hash',
    'oauth_nonce',
    'oauth_timestamp',
    'oauth_consumer_key',
    'oauth_signature_method',
    'oauth_version',
    'oauth_signature',
)

def validate_oauth_nonce(handler):
    # check nonce not previously used
    return handler


def validate_oauth_timestamp(handler):
    timestring = handler.get_argument('oauth_timestamp')
    try:
        request_timestamp = int(timestring)
    except ValueError:
        raise OauthInvalidParamError("Invalid timestamp: %s" % timestring)
    now = time.time()
    ten_min = 60*10
    if request_timestamp < (now - ten_min) or request_timestamp > (now + ten_min):
        raise OauthInvalidParamError("Invalid timestamp: %s" % timestring)
    return handler

def validate_request(handler):
    consumer_key = handler.get_argument('oauth_consumer_key')
    if consumer_key != handler.api_account.consumer_key:
        raise OauthInvalidParamError("Invalid consumer key: %s" % consumer_key)

    params = handler.request.arguments.items()
    single_params = {}
    for param,value in params:
        if isinstance(value, list) and len(value) == 1:
            single_params[param] = value[0]
        else:
            single_params[param] = value

    auth_header = {}
    if 'Authorization' in handler.request.headers:
        auth_header = {
            'Authorization': handler.request.headers['Authorization'],
        }
    req = oauth2.Request.from_request(
        handler.request.method,
        (handler.request.protocol+"://"+handler.request.host+handler.request.uri.split("?")[0]),
        headers=auth_header,
        parameters=single_params,
    )

    try:
        oauth_account = convert_account_to_oauth_account(handler.api_account)
        oauth_server.verify_request(req, oauth_account, None)
        return True
    except oauth2.Error, e:
        self.http_status = 403
        self._errors['oauth'] = ['5|Unauthorized']
    except KeyError, e:
        self._errors['oauth'] = ["5|You failed to supply the "\
                               "necessary parameters (%s) to "\
                               "properly authenticate"]

def validate_oauth_request(handler):
    # ensure that all params are present
    for required_oauth_param in required_oauth_params:
        handler.get_argument(required_oauth_param)
    validate_request(
        validate_oauth_nonce(
            validate_oauth_timestamp(handler)
        )
    )
