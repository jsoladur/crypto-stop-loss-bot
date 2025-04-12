from abc import ABCMeta, abstractmethod
from typing import Any

from httpx import URL, AsyncClient, Response


class AbstractHttpRemoteAsyncService(metaclass=ABCMeta):
    async def _perform_http_request(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
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
            client (AsyncClient, optional): AsyncClient instance. Defaults to None.
        Returns:
            Response: httpx.Response instance
        """
        method, url, params, headers = await self._apply_interceptor(
            method=method, url=url, params=params, headers=headers
        )
        if client:  # pragma: no cover
            response = await client.request(
                method=method, url=url, params=params, headers=headers, **kwargs
            )
        else:
            async with await self.get_http_client() as client:
                response = await client.request(
                    method=method, url=url, params=params, headers=headers, **kwargs
                )
        return response

    async def _apply_interceptor(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
    ) -> tuple[str, URL | str, dict[str, Any] | None, dict[str, Any] | None]:
        """
        Method to apply an interceptor to the given request
        Args:
            method (str, optional): HTTP method. Defaults to "GET".
            url (URL | str, optional): URL to call. Defaults to "/".
            params (dict[str, Any] | None, optional): Params to pass. Defaults to {}.

        return method, url, params, headers
        """
        return method, url, params, headers

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
