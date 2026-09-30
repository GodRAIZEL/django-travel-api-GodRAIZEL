"""Custom DRF exception handler for consistent error responses."""
import logging

from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wrap DRF's default exception handler so every error response has a
    consistent shape: {"error": {"detail": ..., "status_code": ...}}.
    Unhandled (non-APIException) errors are logged and turned into a
    generic 500 response instead of leaking a traceback to the client.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        response.data = {
            'error': {
                'detail': response.data,
                'status_code': response.status_code,
            }
        }
        return response

    # Anything DRF didn't already turn into a Response (e.g. a bare
    # Python exception raised from inside a view) is logged server-side.
    logger.exception('Unhandled exception in view', exc_info=exc)
    return None
