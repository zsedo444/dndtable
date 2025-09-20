from wsgiref.simple_server import make_server

from app import views  # noqa: F401 - ensure routes are registered
from app.database import initialize
from app.router import app


def main():
    initialize()
    with make_server("0.0.0.0", 8000, app) as server:
        print("Serving on http://0.0.0.0:8000")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
