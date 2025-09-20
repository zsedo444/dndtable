import re
from typing import Callable, Dict, List, Optional, Tuple

from .auth import session_manager
from .database import get_user
from .http import Request, Response, parse_request


RouteHandler = Callable[[Request, Dict[str, str]], Response]


class Route:
    def __init__(self, path: str, methods: List[str], handler: RouteHandler):
        self.path = path
        self.methods = methods
        self.handler = handler
        self.pattern, self.param_names = self._compile(path)

    @staticmethod
    def _compile(path: str) -> Tuple[re.Pattern, List[str]]:
        param_regex = re.compile(r"<(?:(int):)?(\w+)>")

        def repl(match: re.Match):
            type_, name = match.groups()
            if type_ == "int":
                return f"(?P<{name}>\\d+)"
            return f"(?P<{name}>[^/]+)"

        pattern = "^" + param_regex.sub(repl, path) + "$"
        compiled = re.compile(pattern)
        names = [m.group(2) for m in param_regex.finditer(path)]
        return compiled, names

    def matches(self, path: str) -> Optional[Dict[str, str]]:
        match = self.pattern.match(path)
        if not match:
            return None
        return match.groupdict()


class Application:
    def __init__(self):
        self.routes: List[Route] = []

    def route(self, path: str, methods: Optional[List[str]] = None):
        if methods is None:
            methods = ["GET"]

        def decorator(func: RouteHandler):
            self.routes.append(Route(path, [m.upper() for m in methods], func))
            return func

        return decorator

    def __call__(self, environ, start_response):
        request = parse_request(environ, session_manager.load_from_headers)
        if request.session and "user_id" in request.session:
            user = get_user(int(request.session["user_id"]))
            if user:
                request.user = dict(user)
        path = request.path
        method = request.method
        for route in self.routes:
            params = route.matches(path)
            if params is None:
                continue
            if method not in route.methods:
                continue
            response = route.handler(request, params)
            return response.start(start_response)
        response = Response("<h1>Not Found</h1>", status="404 Not Found")
        return response.start(start_response)


app = Application()
