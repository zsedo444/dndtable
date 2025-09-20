from datetime import datetime, timedelta
from urllib.parse import urlencode

from .auth import PasswordHasher, session_manager
from .database import (
    add_membership,
    clone_game,
    create_character,
    create_game,
    create_user,
    get_game,
    get_membership,
    get_user_by_email,
    list_all_games,
    list_characters,
    list_memberships,
    list_users_by_role,
    set_game_finalized,
    set_default_attendees,
    update_game,
)
from .http import Request, Response
from .router import app
from .config import BASE_DIR
from .utils import calculate_end_time, escape, format_datetime, month_bounds, render_template

ROLE_LABELS = {
    "admin": "Admin",
    "dungeon_master": "Dungeon Master",
    "adventurer": "Adventurer",
}


def redirect(location: str, message: str | None = None) -> Response:
    if message:
        separator = "&" if "?" in location else "?"
        location = f"{location}{separator}{urlencode({'msg': message})}"
    return Response("", status="302 Found", headers={"Location": location})


def require_login(request: Request) -> Response | None:
    if not request.user:
        next_url = request.path
        if request.query_params:
            next_url += "?" + urlencode(request.query_params)
        return redirect(f"/login?{urlencode({'next': next_url})}")
    return None


def require_role(request: Request, roles: set[str]) -> Response | None:
    if not request.user or request.user.get("role") not in roles:
        return redirect("/", "You do not have permission to access that page.")
    return None


def current_message(request: Request) -> str:
    return request.query_params.get("msg", "")


def render_page(request: Request, title: str, content: str) -> Response:
    navigation_items = []
    if request.user:
        navigation_items.append('<a href="/">Calendar</a>')
        if request.user.get("role") in {"admin", "dungeon_master"}:
            navigation_items.append('<a href="/games/new">New Game</a>')
        if request.user.get("role") == "dungeon_master":
            navigation_items.append('<a href="/games">Manage Games</a>')
        if request.user.get("role") == "adventurer":
            navigation_items.append('<a href="/characters">My Characters</a>')
        navigation_items.append('<a href="/logout">Log out</a>')
    else:
        navigation_items.append('<a href="/login">Log in</a>')
        navigation_items.append('<a href="/register">Register</a>')
    navigation_html = " | ".join(navigation_items)
    message = current_message(request)
    flash_html = f'<div class="flash">{escape(message)}</div>' if message else ""
    if request.user:
        label = ROLE_LABELS.get(request.user.get("role"), "")
        user_info = f"{escape(request.user.get('display_name'))} ({escape(label)})"
    else:
        user_info = ""
    body = render_template(
        "base.html",
        title=escape(title),
        navigation=navigation_html,
        content=flash_html + content,
        user_info=user_info,
    )
    return Response(body)


@app.route("/register", methods=["GET", "POST"])
def register(request: Request, params: dict[str, str]) -> Response:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip() or email
        role = request.form.get("role", "adventurer")
        allow_role_selection = request.user and request.user.get("role") == "admin"
        selected_role = role if allow_role_selection and role in ROLE_LABELS else "adventurer"
        if not email or not password:
            return render_page(
                request,
                "Register",
                register_form_html(error="Email and password are required.", allow_role=allow_role_selection),
            )
        existing = get_user_by_email(email)
        if existing:
            return render_page(
                request,
                "Register",
                register_form_html(error="Email already registered.", allow_role=allow_role_selection),
            )
        password_hash = PasswordHasher.hash_password(password)
        create_user(email, password_hash, display_name, selected_role)
        return redirect("/login", "Registration successful. Please log in.")
    allow_role = request.user and request.user.get("role") == "admin"
    return render_page(request, "Register", register_form_html(allow_role=allow_role))


def register_form_html(error: str = "", allow_role: bool = False) -> str:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    role_selector = ""
    if allow_role:
        options = ''.join(
            f'<option value="{escape(key)}" {"selected" if key == "adventurer" else ""}>{escape(label)}</option>'
            for key, label in ROLE_LABELS.items()
        )
        role_selector = (
            '<label for="role">Role</label>'
            '<select name="role" id="role">'
            f'{options}</select>'
        )
    return (
        "<h1>Register</h1>"
        f"{error_html}"
        "<form method=\"post\" class=\"form\">"
        '<label for="display_name">Display name</label>'
        '<input type="text" id="display_name" name="display_name" required>'
        '<label for="email">Email</label>'
        '<input type="email" id="email" name="email" required>'
        '<label for="password">Password</label>'
        '<input type="password" id="password" name="password" required>'
        f"{role_selector}"
        '<button type="submit">Create account</button>'
        "</form>"
    )


@app.route("/login", methods=["GET", "POST"])
def login(request: Request, params: dict[str, str]) -> Response:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if not user or not PasswordHasher.verify_password(password, user["password_hash"]):
            return render_page(request, "Log in", login_form_html(error="Invalid credentials."))
        session_token = session_manager.serialize({"user_id": user["id"]})
        destination = request.query_params.get("next") or "/"
        response = redirect(destination, "Welcome back!")
        response.set_cookie(session_manager.cookie_name, session_token, max_age=7 * 24 * 3600)
        return response
    return render_page(request, "Log in", login_form_html())


def login_form_html(error: str = "") -> str:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    return (
        "<h1>Log in</h1>"
        f"{error_html}"
        "<form method=\"post\" class=\"form\">"
        '<label for="email">Email</label>'
        '<input type="email" id="email" name="email" required>'
        '<label for="password">Password</label>'
        '<input type="password" id="password" name="password" required>'
        '<button type="submit">Log in</button>'
        "</form>"
    )


@app.route("/logout")
def logout(request: Request, params: dict[str, str]) -> Response:
    response = redirect("/login", "You have been logged out.")
    response.delete_cookie(session_manager.cookie_name)
    return response


@app.route("/")
def dashboard(request: Request, params: dict[str, str]) -> Response:
    if not request.user:
        return redirect("/login")
    return render_page(request, "Game Calendar", calendar_view_html(request))


@app.route("/static/styles.css")
def styles(request: Request, params: dict[str, str]) -> Response:
    css_path = BASE_DIR / "app" / "static" / "styles.css"
    content = css_path.read_text(encoding="utf-8")
    return Response(content, headers={"Content-Type": "text/css"})


def calendar_view_html(request: Request) -> str:
    today = datetime.utcnow()
    month_param = request.query_params.get("month")
    if month_param:
        try:
            today = datetime.strptime(month_param + "-01", "%Y-%m-%d")
        except ValueError:
            today = datetime.utcnow()
    start, end = month_bounds(today)
    games = list_all_games()
    events_by_date: dict[str, list[dict]] = {}
    for game in games:
        date_key = game["start_time"][:10]
        events_by_date.setdefault(date_key, []).append(game)
    first_day = start
    while first_day.weekday() != 0:
        first_day -= timedelta(days=1)
    last_day = end
    while last_day.weekday() != 6:
        last_day += timedelta(days=1)
    rows = []
    current = first_day
    while current <= last_day:
        cells = []
        for _ in range(7):
            date_str = current.strftime("%Y-%m-%d")
            day_num = current.day
            classes = []
            if current.month != today.month:
                classes.append("other-month")
            if date_str == datetime.utcnow().strftime("%Y-%m-%d"):
                classes.append("today")
            events_html = ""
            for event in events_by_date.get(date_str, []):
                events_html += (
                    '<div class="event">'
                    f'<a href="/games/{event["id"]}">{escape(event["name"])}</a>'
                    f'<span class="time">{format_datetime(event["start_time"])} - {calculate_end_time(event["start_time"], event["duration_minutes"])}</span>'
                    '</div>'
                )
            cell_html = (
                f'<td class="{" ".join(classes)}">'
                f'<div class="date">{day_num}</div>'
                f'{events_html}'
                '</td>'
            )
            cells.append(cell_html)
            current += timedelta(days=1)
        rows.append("<tr>" + "".join(cells) + "</tr>")
    prev_month = (today - timedelta(days=1)).strftime("%Y-%m")
    next_month = (today + timedelta(days=32)).strftime("%Y-%m")
    return (
        '<div class="calendar-header">'
        f'<a class="button" href="/?month={prev_month}">Previous</a>'
        f'<h1>{today.strftime("%B %Y")}</h1>'
        f'<a class="button" href="/?month={next_month}">Next</a>'
        '</div>'
        '<table class="calendar">'
        '<thead><tr>'
        + ''.join(f'<th>{day}</th>' for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        + '</tr></thead>'
        + '<tbody>' + ''.join(rows) + '</tbody>'
        + '</table>'
    )


@app.route("/games")
def games_index(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"dungeon_master", "admin"})
    if permission:
        return permission
    games = list_all_games()
    rows = []
    for game in games:
        rows.append(
            '<tr>'
            f'<td><a href="/games/{game["id"]}">{escape(game["name"])}</a></td>'
            f'<td>{format_datetime(game["start_time"])}</td>'
            f'<td>{game["duration_minutes"]} min</td>'
            f'<td>{game["max_seats"]}</td>'
            f'<td>{"Yes" if game["is_finalized"] else "No"}</td>'
            '</tr>'
        )
    table_html = (
        '<h1>Manage Games</h1>'
        '<table class="data-table">'
        '<thead><tr><th>Name</th><th>Start</th><th>Duration</th><th>Seats</th><th>Finalized</th></tr></thead>'
        f'<tbody>{"".join(rows) if rows else "<tr><td colspan=5>No games scheduled.</td></tr>"}</tbody>'
        '</table>'
    )
    return render_page(request, "Games", table_html)


@app.route("/games/new", methods=["GET", "POST"])
def create_game_view(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"dungeon_master", "admin"})
    if permission:
        return permission
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_time = request.form.get("start_time", "")
        duration = int(request.form.get("duration", "0") or 0)
        max_seats = int(request.form.get("max_seats", "0") or 0)
        default_adventurers = [int(uid) for uid in request.form.get("defaults", "").split(",") if uid]
        try:
            datetime.fromisoformat(start_time)
        except ValueError:
            start_time = ""
        if not name or not start_time:
            return render_page(
                request,
                "New Game",
                game_form_html(list_users_by_role("adventurer"), error="Name and start time are required."),
            )
        game_id = create_game(name, start_time, duration, max_seats, request.user["id"])
        set_default_attendees(game_id, default_adventurers)
        return redirect(f"/games/{game_id}", "Game created successfully.")
    adventurers = list_users_by_role("adventurer")
    return render_page(request, "New Game", game_form_html(adventurers))


def game_form_html(adventurers, game=None, error: str = "") -> str:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    name_val = escape(game["name"]) if game else ""
    start_val = escape(game["start_time"]) if game else ""
    duration_val = game["duration_minutes"] if game else 180
    max_seats_val = game["max_seats"] if game else 6
    selected_defaults = {m["user_id"] for m in list_memberships(game["id"]) if m["is_default"]} if game else set()
    options = []
    for adventurer in adventurers:
        selected = "checked" if adventurer["id"] in selected_defaults else ""
        options.append(
            '<label class="checkbox">'
            f'<input type="checkbox" name="default_ids" value="{adventurer["id"]}" {selected}>'
            f'{escape(adventurer["display_name"])} ({escape(adventurer["email"])})'
            '</label>'
        )
    defaults_html = ''.join(options) if options else '<p>No adventurers available.</p>'
    hidden_defaults = ','.join(str(uid) for uid in selected_defaults) if selected_defaults else ''
    script = (
        "<script>"
        "function collectDefaults(event){"
        "  const values = Array.from(document.querySelectorAll(\"input[name='default_ids']\"))"
        "    .filter(cb => cb.checked)"
        "    .map(cb => cb.value);"
        "  document.getElementById(\"defaults\").value = values.join(\",\");"
        "}"
        "</script>"
    )
    return (
        '<h1>Game Details</h1>'
        f'{error_html}'
        '<form method="post" class="form" onsubmit="collectDefaults(event)">' 
        f'<label for="name">Name</label><input type="text" name="name" id="name" value="{name_val}" required>'
        f'<label for="start_time">Start time (YYYY-MM-DDTHH:MM)</label>'
        f'<input type="text" name="start_time" id="start_time" value="{start_val}" placeholder="2024-01-01T18:00" required>'
        f'<label for="duration">Duration (minutes)</label>'
        f'<input type="number" name="duration" id="duration" value="{duration_val}" min="30" step="15" required>'
        f'<label for="max_seats">Max seats</label>'
        f'<input type="number" name="max_seats" id="max_seats" value="{max_seats_val}" min="1" required>'
        '<fieldset><legend>Default adventurers</legend>'
        f'{defaults_html}'
        '</fieldset>'
        f'<input type="hidden" name="defaults" id="defaults" value="{hidden_defaults}">' 
        '<button type="submit">Save</button>'
        '</form>'
        f'{script}'
    )


@app.route("/games/<int:game_id>")
def game_detail(request: Request, params: dict[str, str]) -> Response:
    permission = require_login(request)
    if permission:
        return permission
    game_id = int(params["game_id"])
    game = get_game(game_id)
    if not game:
        return render_page(request, "Game", '<p class="error">Game not found.</p>')
    memberships = list_memberships(game_id)
    attendee_rows = []
    for membership in memberships:
        default_label = " (default)" if membership["is_default"] else ""
        attendee_rows.append(
            '<tr>'
            f'<td>{escape(membership["display_name"])}</td>'
            f'<td>{escape(membership["email"])}</td>'
            f'<td>{membership["status"].title()}</td>'
            f'<td>{default_label}</td>'
            '</tr>'
        )
    attendees_table = (
        '<h2>Attendees</h2>'
        '<table class="data-table">'
        '<thead><tr><th>Name</th><th>Email</th><th>Status</th><th>Default</th></tr></thead>'
        f'<tbody>{"".join(attendee_rows) if attendee_rows else "<tr><td colspan=4>No adventurers yet.</td></tr>"}</tbody>'
        '</table>'
    )
    action_buttons = []
    if request.user.get("role") in {"dungeon_master", "admin"}:
        action_buttons.append(f'<a class="button" href="/games/{game_id}/edit">Edit</a>')
        action_buttons.append(f'<a class="button" href="/games/{game_id}/clone">Clone</a>')
        if not game["is_finalized"]:
            action_buttons.append(f'<a class="button" href="/games/{game_id}/finalize">Finalize</a>')
    if request.user.get("role") == "adventurer" and not game["is_finalized"]:
        membership = get_membership(game_id, request.user["id"])
        if membership and membership["status"] == "invited":
            action_buttons.append(f'<a class="button" href="/games/{game_id}/join">Join Game</a>')
        elif membership and membership["status"] == "joined":
            action_buttons.append(f'<a class="button" href="/games/{game_id}/confirm">Confirm Attendance</a>')
        elif not membership:
            action_buttons.append(f'<a class="button" href="/games/{game_id}/join">Join Game</a>')
    action_html = '<div class="actions">' + ''.join(action_buttons) + '</div>' if action_buttons else ''
    game_info = (
        '<h1>Game Details</h1>'
        f'<p><strong>Name:</strong> {escape(game["name"])}</p>'
        f'<p><strong>Start:</strong> {format_datetime(game["start_time"])}</p>'
        f'<p><strong>End:</strong> {calculate_end_time(game["start_time"], game["duration_minutes"])}</p>'
        f'<p><strong>Duration:</strong> {game["duration_minutes"]} minutes</p>'
        f'<p><strong>Max seats:</strong> {game["max_seats"]}</p>'
        f'<p><strong>Finalized:</strong> {"Yes" if game["is_finalized"] else "No"}</p>'
        f'{action_html}'
    )
    return render_page(request, "Game", game_info + attendees_table)


@app.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit_game(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"dungeon_master", "admin"})
    if permission:
        return permission
    game_id = int(params["game_id"])
    game = get_game(game_id)
    if not game:
        return redirect("/games", "Game not found.")
    adventurers = list_users_by_role("adventurer")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_time = request.form.get("start_time", "")
        duration = int(request.form.get("duration", "0") or 0)
        max_seats = int(request.form.get("max_seats", "0") or 0)
        default_adventurers = [int(uid) for uid in request.form.get("defaults", "").split(",") if uid]
        try:
            datetime.fromisoformat(start_time)
        except ValueError:
            start_time = ""
        if not name or not start_time:
            return render_page(
                request,
                "Edit Game",
                game_form_html(adventurers, game=game, error="Name and start time are required."),
            )
        update_game(game_id, name, start_time, duration, max_seats)
        set_default_attendees(game_id, default_adventurers)
        return redirect(f"/games/{game_id}", "Game updated.")
    return render_page(request, "Edit Game", game_form_html(adventurers, game=game))


@app.route("/games/<int:game_id>/clone")
def clone_game_view(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"dungeon_master", "admin"})
    if permission:
        return permission
    game_id = int(params["game_id"])
    new_game_id = clone_game(game_id, request.user["id"])
    if not new_game_id:
        return redirect("/games", "Unable to clone game.")
    return redirect(f"/games/{new_game_id}", "Game cloned. Update details before finalizing.")


@app.route("/games/<int:game_id>/finalize")
def finalize_game(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"dungeon_master", "admin"})
    if permission:
        return permission
    game_id = int(params["game_id"])
    set_game_finalized(game_id, True)
    return redirect(f"/games/{game_id}", "Game finalized.")


@app.route("/games/<int:game_id>/join")
def join_game(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"adventurer"})
    if permission:
        return permission
    game_id = int(params["game_id"])
    game = get_game(game_id)
    if not game or game["is_finalized"]:
        return redirect("/", "Cannot join this game.")
    membership = get_membership(game_id, request.user["id"])
    memberships = list_memberships(game_id)
    active_count = sum(1 for m in memberships if m["status"] in {"joined", "confirmed"} and m["user_id"] != request.user["id"])
    if membership and membership["status"] in {"joined", "confirmed"}:
        active_count += 1
    if not membership and active_count >= game["max_seats"]:
        return redirect(f"/games/{game_id}", "This game is already at capacity.")
    add_membership(game_id, request.user["id"], "joined", is_default=bool(membership and membership["is_default"]))
    return redirect(f"/games/{game_id}", "You have joined the game. Confirm attendance when ready.")


@app.route("/games/<int:game_id>/confirm")
def confirm_game(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"adventurer"})
    if permission:
        return permission
    game_id = int(params["game_id"])
    game = get_game(game_id)
    if not game or game["is_finalized"]:
        return redirect("/", "Cannot confirm this game.")
    membership = get_membership(game_id, request.user["id"])
    if not membership or membership["status"] not in {"joined", "invited"}:
        return redirect(f"/games/{game_id}", "You need to join the game first.")
    add_membership(game_id, request.user["id"], "confirmed", is_default=bool(membership["is_default"]))
    return redirect(f"/games/{game_id}", "Attendance confirmed. See you there!")


@app.route("/characters")
def characters_index(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"adventurer"})
    if permission:
        return permission
    characters = list_characters(request.user["id"])
    rows = []
    for character in characters:
        rows.append(
            '<tr>'
            f'<td>{escape(character["name"])}</td>'
            f'<td>{escape(character["class_name"])}</td>'
            '</tr>'
        )
    table_html = (
        '<h1>My Characters</h1>'
        '<a class="button" href="/characters/new">Create character</a>'
        '<table class="data-table">'
        '<thead><tr><th>Name</th><th>Class</th></tr></thead>'
        f'<tbody>{"".join(rows) if rows else "<tr><td colspan=2>No characters yet.</td></tr>"}</tbody>'
        '</table>'
    )
    return render_page(request, "Characters", table_html)


@app.route("/characters/new", methods=["GET", "POST"])
def create_character_view(request: Request, params: dict[str, str]) -> Response:
    permission = require_role(request, {"adventurer"})
    if permission:
        return permission
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        if not name or not class_name:
            return render_page(request, "New Character", character_form_html(error="All fields are required."))
        create_character(request.user["id"], name, class_name)
        return redirect("/characters", "Character created.")
    return render_page(request, "New Character", character_form_html())


def character_form_html(error: str = "") -> str:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    return (
        '<h1>New Character</h1>'
        f'{error_html}'
        '<form method="post" class="form">'
        '<label for="name">Name</label>'
        '<input type="text" id="name" name="name" required>'
        '<label for="class_name">Class</label>'
        '<input type="text" id="class_name" name="class_name" required>'
        '<button type="submit">Save</button>'
        '</form>'
    )
