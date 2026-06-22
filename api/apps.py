from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Called once when Django starts — connect to Atlas and create indexes."""
        try:
            from .db import ensure_indexes, ping
            result = ping()
            if result['status'] == 'connected':
                logger.info(
                    "✅ MongoDB Atlas connected — DB: %s | Collections: %d",
                    result['database'],
                    result['collections_count'],
                )
                ensure_indexes()
            else:
                logger.error("❌ MongoDB Atlas connection failed: %s", result.get('error'))
        except Exception as exc:
            logger.error("MongoDB Atlas startup error: %s", exc)
