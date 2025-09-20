import cgi
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Dict, Optional
from urllib.parse import parse_qs


@dataclass
class Request:
    method: str
    path: str
    query_params: Dict[str, str]
    form: Dict[str, str]
    headers: Dict[str, str]
    session: Optional[dict]
    user: Optional[dict]
    raw_environ: dict


class Response:
    def __init__(self, body: str = "", status: str = "200 OK", headers: Optional[Dict[str, str]] = None):
        self.body = body.encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        if headers:
            self.headers.update(headers)
        self.cookies = []

    def set_cookie(self, key: str, value: str, max_age: Optional[int] = None, path: str = "/"):
        cookie = f"{key}={value}; Path={path}; HttpOnly"
        if max_age is not None:
            cookie += f"; Max-Age={max_age}"
        self.cookies.append(cookie)

    def delete_cookie(self, key: str, path: str = "/"):
        self.cookies.append(f"{key}=; Path={path}; Max-Age=0")

    def start(self, start_response: Callable):
        headers_list = list(self.headers.items())
        for cookie in self.cookies:
            headers_list.append(("Set-Cookie", cookie))
        start_response(self.status, headers_list)
        return [self.body]


def parse_request(environ: dict, session_loader: Callable[[dict], Optional[dict]]):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    query_params = {k: v[0] for k, v in parse_qs(query).items()}
    headers = {key: value for key, value in environ.items() if key.startswith("HTTP_")}

    form_data: Dict[str, str] = {}
    if method in {"POST", "PUT"}:
        try:
            size = int(environ.get("CONTENT_LENGTH", 0))
        except (ValueError, TypeError):
            size = 0
        body = environ.get("wsgi.input", BytesIO()).read(size)
        environ_copy = environ.copy()
        environ_copy["wsgi.input"] = BytesIO(body)
        fp = environ_copy["wsgi.input"]
        content_type = environ.get("CONTENT_TYPE", "application/x-www-form-urlencoded")
        if content_type.startswith("application/x-www-form-urlencoded"):
            form_data = {k: v[0] for k, v in parse_qs(body.decode("utf-8")).items()}
        elif content_type.startswith("multipart/form-data"):
            fs = cgi.FieldStorage(fp=fp, environ=environ_copy, keep_blank_values=True)
            for field in fs.list or []:
                form_data[field.name] = field.value
    session = session_loader(environ)
    return Request(
        method=method,
        path=path,
        query_params=query_params,
        form=form_data,
        headers=headers,
        session=session,
        user=None,
        raw_environ=environ,
    )
