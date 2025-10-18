from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlencode

from httpx import URL, AsyncClient, Response


class AbstractHttpRemoteAsyncService(ABC):
    async def _perform_http_request(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
        client: AsyncClient = None,
        **kwargs,
    ) -> Response:
        """
        Method to perform a HTTP request to the given URL
        Args:
            method (str, optional): HTTP method. Defaults to "GET".
            url (URL | str, optional): URL to call. Defaults to "/".
            params (dict[str, Any] | None, optional): Params to pass. Defaults to {}.
            headers (dict[str, Any] | None, optional): Headers to pass. Defaults to {}.
            body (Any | None, optional): JSON to pass. Defaults to None.
            client (AsyncClient, optional): AsyncClient instance. Defaults to None.
        Returns:
            Response: httpx.Response instance
        """
        params, headers = await self._apply_request_interceptor(
            method=method, url=url, params=params, headers=headers, body=body
        )
        if client:
            response = await client.request(method=method, url=url, params=params, headers=headers, json=body, **kwargs)
        else:  # pragma: no cover
            async with await self.get_http_client() as client:
                response = await client.request(
                    method=method, url=url, params=params, headers=headers, json=body, **kwargs
                )
        response = await self._apply_response_interceptor(
            method=method, url=url, params=params, headers=headers, body=body, response=response
        )
        return response

    async def _apply_request_interceptor(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
    ) -> tuple[str, URL | str, dict[str, Any] | None, dict[str, Any] | None]:
        """
        Method to apply an interceptor to the given request
        Args:
            method (str, optional): HTTP method. Defaults to "GET".
            url (URL | str, optional): URL to call. Defaults to "/".
            params (dict[str, Any] | None, optional): Params to pass. Defaults to {}.
            headers (dict[str, Any] | None, optional): Headers to pass. Defaults to {}.
            json (Any | None, optional): Json paylaod as a Http Request body. Defaults to None.

        Returns:
            tuple[str, URL | str, dict[str, Any] | None, dict[str, Any] | None]:
                tuple of params and headers
        """
        return params, headers

    async def _apply_response_interceptor(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
        response: Response,
    ) -> Response:
        """
        Method to apply an interceptor to the given response
        Args:
            method (str, optional): HTTP method. Defaults to "GET".
            url (URL | str, optional): URL to call. Defaults to "/".
            params (dict[str, Any] | None, optional): Params to pass. Defaults to {}.
            headers (dict[str, Any] | None, optional): Headers to pass. Defaults to {}.
            json (Any | None, optional): Json paylaod as a Http Request body. Defaults to None.
            response (Response): HTTP response. Defaults to "GET".
        Returns:
            Response: HTTP response
        """
        return response

    @abstractmethod
    async def get_http_client(self) -> AsyncClient:
        """
        Method to create a new HTTP asyncio client for calling
        to the expected external remote RESTful services

        Note that you have to pass to the newly Http Client
        the param httpx.AsyncClient(..., mounts=self._proxies, ...)
        in order to use proxies configuration if it is needed.

        Returns:
            AsyncClient: httpx.AsyncClient new instance
        """

    def _build_full_url(self, path: str, query_params: dict[str, any]) -> str:
        full_url = path
        if query_params:
            query_string = urlencode(query_params, doseq=True)
            full_url += "?" + query_string
        return full_url
