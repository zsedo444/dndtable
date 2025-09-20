# DnD Table

DnD Table is a lightweight web application for coordinating Dungeons & Dragons game nights. It is built only with the Python standard library and SQLite so it can run in restricted environments without external dependencies.

## Features

- Email-based registration and login with secure password hashing.
- Three user roles:
  - **Admin** – full access (a default admin account is created automatically).
  - **Dungeon Master** – create, edit, clone and finalize games.
  - **Adventurer** – manage characters, join games and confirm attendance.
- Monthly calendar view showing all scheduled games at a glance.
- Game management with cloning, seat limits and default invitees.
- Attendance tracking with invited, joined and confirmed states.
- Character roster for each adventurer.

## Getting Started

1. Ensure you have Python 3.11 (or newer) available. No third-party dependencies are required.
2. Initialize the database and start the development server:

   ```bash
   python server.py
   ```

   The server listens on `http://0.0.0.0:8000`.

3. Sign in with the default administrator account to configure additional users:

   - **Email:** `admin@example.com`
   - **Password:** `admin123`

   Create dungeon master or adventurer accounts from the registration page (available after logging in as admin).

## Project Structure

```
app/
├── auth.py          # password hashing and cookie-based sessions
├── config.py        # basic configuration values
├── database.py      # SQLite helpers and migrations
├── http.py          # minimal Request/Response helpers
├── router.py        # simple route registration and dispatcher
├── templates/
│   └── base.html    # shared layout template
├── static/
│   └── styles.css   # styling for the UI
└── views.py         # route handlers and page rendering
server.py            # entrypoint that runs the WSGI server
README.md            # documentation
```

## Running Tests

The project currently relies on manual testing via the running server. Automated tests can be added under the `tests/` folder and executed with `python -m unittest` when available.

## Notes

- Because the application serves static files through the Python process, it is intended for small groups and development usage. For production setups, place it behind a proper HTTP server capable of caching static assets.
- Passwords are hashed using PBKDF2-HMAC with a secret-key-derived salt. Change the `DNDTABLE_SECRET_KEY` environment variable in production environments for additional security.
