"""HTTP client for the local workbench; never invokes a model itself."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WorkbenchError(RuntimeError):
    pass


class WorkbenchClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def request(self, path, payload=None, *, raw=False):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + "/api/v1" + path, data=body,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                data = response.read()
            return data if raw else json.loads(data)
        except HTTPError as error:
            try:
                code = json.loads(error.read())["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = "HTTP_" + str(error.code)
            raise WorkbenchError(code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise WorkbenchError("API_UNAVAILABLE") from None
