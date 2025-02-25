from fasthtml.common import *
from datetime import datetime
from utils import standardize_column


db = database("data/quran.db")

revisions, users = db.t.revisions, db.t.users
if revisions not in db.t:
    users.create(user_id=int, name=str, email=str, password=str, pk="user_id")
    revisions.create(
        id=int,
        user_id=int,
        page=int,
        revision_time=str,
        rating=str,
        created_by=str,
        created_at=str,
        last_modified_by=str,
        last_modified_at=str,
        pk="id",
    )
Revision, User = revisions.dataclass(), users.dataclass()


login_redir = RedirectResponse("/login", status_code=303)
home_redir = RedirectResponse("/", status_code=303)
revision_redir = RedirectResponse("/revision", status_code=303)


def before(req, sess):
    auth = req.scope["auth"] = sess.get("auth", None)
    id = sess.get("user_id", None)
    if not auth:
        return login_redir
    revisions.xtra(user_id=id)


bware = Beforeware(
    before, skip=[r"/favicon\.ico", r"/static/.*", r".*\.css", "/login", "/signup"]
)

app, rt = fast_app(live=True, before=bware)
setup_toasts(app)


column_headers = [
    "Select",
    "Page",
    "Revision Time",
    "Rating",
    "Created By",
    "Created At",
    "Last Modified By",
    "Last Modified At",
]

column_standardized = list(map(standardize_column, column_headers))[1:]

current_time = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def radio_btn(id, state=False):
    return Input(
        type="radio",
        name="revision_id",
        value=id,
        id=f"r-{id}",
        hx_swap_oob="true",
        checked=state,
    )


def render_revision_row(revision):
    # Convert the revision object to a dictionary to easily access its attributes by column names
    rev_dict = vars(revision)
    id = rev_dict["id"]
    rid = f"r-{id}"

    return Tr(
        Td(radio_btn(id)),
        *[Td(rev_dict[c]) for c in column_standardized],
        hx_get=select.to(id=id),
        target_id=rid,
        hx_swap="outerHTML",
        id=f"row-{id}",
    )


def get_first_unique_page() -> list[dict]:
    unique_pages = set()
    result = []
    for r in revisions(order_by="revision_time DESC"):
        if r.page not in unique_pages:
            unique_pages.add(r.page)
            result.append(r.__dict__)
    # Reverse the list to get the oldest first
    return result[::-1]


@app.get
def signup():
    return Titled(
        "Sign up",
        Form(
            Input(name="name", placeholder="Name", required=True),
            Input(type="email", name="email", placeholder="Email", required=True),
            Input(
                type="password", name="password", placeholder="Password", required=True
            ),
            Button("sign up"),
            action=signup,
            method="POST",
        ),
    )


@app.post
def signup(user: User, sess):
    try:
        u = users(where=f"email = '{user.email}'")[0]
    except IndexError:
        u = users.insert(user)
    else:
        add_toast(sess, "This email is already registered", "info")
        return login_redir

    sess["auth"] = u.name
    sess["user_id"] = u.user_id
    return home_redir


@app.get
def login():
    return Titled(
        "Login",
        Form(
            Input(type="email", name="email", placeholder="Email", required=True),
            Input(
                type="password", name="password", placeholder="Password", required=True
            ),
            Button("login"),
            action=login,
            method="POST",
        ),
    )


@dataclass
class Login:
    email: str
    password: str


@app.post
def login(user: Login, sess):
    try:
        u = users(where=f"email = '{user.email}'")[0]
    except IndexError:
        add_toast(sess, "This email is not registered", "warning")
        return RedirectResponse("/signup", status_code=303)

    if not compare_digest(u.password.encode("utf-8"), user.password.encode("utf-8")):
        add_toast(sess, "Incorrect password", "error")
        return login_redir

    sess["auth"] = u.name
    sess["user_id"] = u.user_id
    return home_redir


@rt
def logout(sess):
    del sess["auth"]
    del sess["user_id"]
    return login_redir


def navbar(user, title, active="Home"):
    return (
        Nav(
            Ul(Li(P(Strong("User: "), user))),
            Ul(Li(H3(title))),
            Ul(
                Li(A("Home", href="/", cls=None if active == "Home" else "contrast")),
                Li(
                    A(
                        "Revision",
                        href=revision,
                        cls=None if active == "Revision" else "contrast",
                    )
                ),
                Li(A("logout", href=logout, cls="contrast")),
            ),
        ),
        Hr(),
    )


@rt
def index(auth):
    title = "Quran SRS Home"
    top = navbar(auth, title)
    rows = [Tr(Td(r["page"]), Td(r["revision_time"])) for r in get_first_unique_page()]
    table = Table(Thead(Tr(Th("Page"), Th("Last Revision Time"))), Tbody(*rows))
    return Title(title), Container(
        top,
        Div("Fresh start with FastHTML"),
        table,
    )


edit_btn = lambda disable=True: Button(
    "Edit",
    hx_post=edit,
    hx_target="body",
    hx_swap="outerHTML",
    hx_push_url="true",
    id="editButton",
    cls="secondary",
    disabled=disable,
    hx_swap_oob="true",
)

delete_btn = lambda disable=True: Button(
    "Delete",
    hx_post=delete_row,
    hx_swap="none",
    id="deleteButton",
    cls="secondary",
    disabled=disable,
    hx_swap_oob="true",
)


@rt
def revision(auth):
    title = "Quran SRS Revision"
    new_btn = Button(
        "New",
        hx_get=add_revision,
        hx_target="body",
        hx_swap="outerHTML",
        hx_push_url="true",
    )

    actions = Div(new_btn, " ", edit_btn(), " ", delete_btn())
    table = Table(
        Thead(Tr(*map(Th, column_headers))),
        # Reverse the list to get the last edited first
        Tbody(*map(render_revision_row, revisions(order_by="last_modified_at")[::-1])),
    )
    form = Form(actions, table, cls="overflow-auto")
    return Title(title), Container(navbar(auth, title, active="Revision"), form)


@app.post
def delete_row(revision_id: int):
    revisions.delete(revision_id)
    return (
        Tr(id=f"row-{revision_id}", hx_swap_oob="true"),
        edit_btn(),
        delete_btn(),
    )


@rt
def select(id: int):
    return (
        radio_btn(id, True),
        edit_btn(disable=False),
        delete_btn(disable=False),
    )


@app.post
def edit(revision_id: int):
    return RedirectResponse(f"/edit?id={revision_id}", status_code=303)


def input_form(action: str):
    return Form(
        Hidden(name="id") if action == "update" else None,
        Label("Page", Input(type="number", name="page", autofocus=True)),
        Label(
            "Date",
            Input(
                type="datetime-local",
                name="revision_time",
                value=current_time(),
            ),
        ),
        Label(
            "Rating",
            Select(
                Option("Good", value="Good"),
                Option("Ok", value="Ok"),
                Option("Bad", value="Bad"),
                name="rating",
            ),
        ),
        Button(action.capitalize()),
        action=f"/{action}",
        method="POST",
    )


@app.get
def edit(id: int):
    form = input_form(action="update")
    return Titled("Edit", fill_form(form, revisions[id]))


@app.post
def update(auth, revision: Revision):
    # Clean up the revision_time
    revision.revision_time = revision.revision_time.replace("T", " ")
    revision.last_modified_at = current_time()
    revision.last_modified_by = auth
    revisions.update(revision)
    return revision_redir


@rt
def add_revision():
    return Titled("Add Revision", input_form(action="create"))


@app.post
def create(auth, revision: Revision):
    revision.revision_time = revision.revision_time.replace("T", " ")
    revision.created_at = revision.last_modified_at = current_time()
    revision.created_by = revision.last_modified_by = auth
    revisions.insert(revision)
    return revision_redir


serve()
