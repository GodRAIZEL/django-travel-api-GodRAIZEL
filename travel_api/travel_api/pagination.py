"""Custom pagination classes for the Travel API."""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Default pagination used globally: page size is client-adjustable via
    ?page_size= up to a hard cap, to keep large collections (destinations,
    bookings) from returning unbounded result sets.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


class LargeResultsSetPagination(PageNumberPagination):
    """
    Custom pagination class for endpoints that intentionally return more
    rows per page (e.g. analytics/report style read-only endpoints).
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
