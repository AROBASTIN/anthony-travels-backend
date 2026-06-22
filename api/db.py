"""
MongoDB Atlas Connection Service — Anthony Travels
===================================================
All credentials are loaded from environment variables via Django settings.
Nothing is hardcoded in this file.

Collections exposed:
  users, drivers, cab_owners, admins, vehicles, bookings,
  payments, reviews, faqs, fuel_prices, notifications,
  trip_history, pricing_config, website_content
"""

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Singleton client — one connection per Django process
# ============================================================
_client: MongoClient = None
_db = None


def _connect():
    """Initialise the MongoClient and database handle (idempotent)."""
    global _client, _db
    if _client is not None:
        return

    uri = getattr(settings, 'MONGODB_URI', '')
    if not uri:
        raise ConfigurationError(
            "MONGODB_URI is not configured. "
            "Add it to backend/.env and ensure load_dotenv() runs in settings.py."
        )

    # tlsAllowInvalidCertificates=True works around the Python 3.13 / Windows
    # OpenSSL TLS 1.3 internal error that occurs with Atlas SRV connections.
    # This is safe for development; for production use a proper CA bundle.
    _client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
        tlsAllowInvalidCertificates=True,
    )
    db_name = getattr(settings, 'MONGODB_DB_NAME', 'anthony_travels')
    _db = _client[db_name]
    logger.info("MongoDB Atlas client connected to database: %s", db_name)


def get_db():
    """Return the active database handle, connecting if necessary."""
    _connect()
    return _db


def get_collection(name: str):
    """Return any collection by name."""
    return get_db()[name]


# ============================================================
# Convenience collection accessors
# Each returns the live Collection object every call (cheap ref).
# ============================================================

def _c(name):
    return get_db()[name]


# Properties that resolve to real PyMongo Collection objects
class _ColProxy:
    """Lightweight proxy so `users_col.find(...)` just works."""
    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        return getattr(get_db()[self._name], attr)

    def __repr__(self):
        return f"<ColProxy '{self._name}'>"


users_col           = _ColProxy('users')
drivers_col         = _ColProxy('drivers')
cab_owners_col      = _ColProxy('cab_owners')
admins_col          = _ColProxy('admins')
vehicles_col        = _ColProxy('vehicles')
bookings_col        = _ColProxy('bookings')
payments_col        = _ColProxy('payments')
reviews_col         = _ColProxy('reviews')
faqs_col            = _ColProxy('faqs')
fuel_prices_col     = _ColProxy('fuel_prices')
notifications_col   = _ColProxy('notifications')
trip_history_col    = _ColProxy('trip_history')
pricing_config_col  = _ColProxy('pricing_config')
website_content_col = _ColProxy('website_content')
kyc_documents_col   = _ColProxy('kyc_documents')
verification_requests_col = _ColProxy('verification_requests')
enquiries_col       = _ColProxy('enquiries')


# ============================================================
# Health-check — used by /api/health endpoint
# ============================================================
def ping() -> dict:
    """
    Send a ping to Atlas and return a status dictionary.
    Returns a 'connected' or 'error' status dict.
    """
    try:
        _connect()
        _client.admin.command('ping')
        db = get_db()
        collections = sorted(db.list_collection_names())
        return {
            'status': 'connected',
            'database': db.name,
            'collections': collections,
            'collections_count': len(collections),
        }
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("MongoDB Atlas ping failed: %s", exc)
        return {
            'status': 'error',
            'error': str(exc),
            'database': getattr(settings, 'MONGODB_DB_NAME', 'anthony_travels'),
        }
    except ConfigurationError as exc:
        logger.error("MongoDB configuration error: %s", exc)
        return {'status': 'misconfigured', 'error': str(exc)}
    except Exception as exc:
        logger.error("Unexpected MongoDB error: %s", exc)
        return {'status': 'error', 'error': str(exc)}


# ============================================================
# Index creation — call once at app startup
# ============================================================
def ensure_indexes():
    """
    Create or verify indexes on Atlas collections.
    Safe to call repeatedly — MongoDB is idempotent for existing indexes.
    """
    try:
        db = get_db()
        db['users'].create_index('email', unique=True, sparse=True)
        db['vehicles'].create_index('plate_number', unique=True, sparse=True)
        db['vehicles'].create_index([('approved', 1)])
        db['bookings'].create_index([('customer_id', 1)])
        db['bookings'].create_index([('driver_id', 1)])
        db['bookings'].create_index([('status', 1)])
        db['drivers'].create_index([('user_id', 1)])
        db['payments'].create_index([('booking_id', 1)])
        logger.info("MongoDB Atlas indexes verified.")
    except Exception as exc:
        logger.warning("Index creation warning: %s", exc)
