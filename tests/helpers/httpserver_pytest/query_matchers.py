import urllib.parse
from collections.abc import Mapping

from pytest_httpserver.httpserver import QueryMatcher
from werkzeug.datastructures import MultiDict


class Bit2MeAPIQueryMatcher(QueryMatcher):
    """
    Matches a query string to a dictionary or MultiDict specified
    """

    def __init__(
        self, query_dict: Mapping[str, str] | MultiDict[str, str], *, additional_required_query_params: list[str] = []
    ) -> None:
        self._query_dict = query_dict.to_dict() if isinstance(query_dict, MultiDict) else dict(query_dict)
        self._additional_required_query_params = additional_required_query_params

    def get_comparing_values(self, request_query_string: bytes) -> tuple[bool, bool]:
        received_query = MultiDict(urllib.parse.parse_qsl(request_query_string.decode("utf-8"))).to_dict()

        for query_name, query_value in self._query_dict.items():
            if query_name not in received_query or query_value != received_query[query_name]:
                return (False, False)
        for additional_required_query_param in self._additional_required_query_params:
            if additional_required_query_param not in additional_required_query_param:
                return (False, False)
        return (True, True)
