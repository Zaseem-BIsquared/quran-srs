from fasthtml.common import *
import fasthtml.common as fh
from monsterui.all import *
from utils import *
import pandas as pd
from io import BytesIO
from collections import defaultdict

RATING_MAP = {"1": "✅ Good", "0": "😄 Ok", "-1": "❌ Bad"}
OPTION_MAP = {
    "role": ["hafiz", "parent", "teacher", "parent_hafiz"],
    "age_group": ["child", "teen", "adult"],
    "relationship": ["self", "parent", "teacher", "sibling"],
}
DB_PATH = "data/quran_v8.db"

# This function will handle table creation and migration using fastmigrate
create_and_migrate_db(DB_PATH)

db = database(DB_PATH)
tables = db.t
(
    revisions,
    hafizs,
    users,
    hafizs_users,
    plans,
    modes,
    pages,
    surahs,
    items,
    mushafs,
    hafizs_items,
) = (
    tables.revisions,
    tables.hafizs,
    tables.users,
    tables.hafizs_users,
    tables.plans,
    tables.modes,
    tables.pages,
    tables.surahs,
    tables.items,
    tables.mushafs,
    tables.hafizs_items,
)
(
    Revision,
    Hafiz,
    User,
    Hafiz_Users,
    Plan,
    Mode,
    Page,
    Item,
    Surah,
    Mushaf,
    Hafiz_Items,
) = (
    revisions.dataclass(),
    hafizs.dataclass(),
    users.dataclass(),
    hafizs_users.dataclass(),
    plans.dataclass(),
    modes.dataclass(),
    pages.dataclass(),
    items.dataclass(),
    surahs.dataclass(),
    mushafs.dataclass(),
    hafizs_items.dataclass(),
)


hyperscript_header = Script(src="https://unpkg.com/hyperscript.org@0.9.14")
alpinejs_header = Script(
    src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js", defer=True
)


def before(req, sess):
    user_auth = req.scope["user_auth"] = sess.get("user_auth", None)
    if not user_auth:
        return RedirectResponse("/login", status_code=303)
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return RedirectResponse("/hafiz_selection", status_code=303)
    revisions.xtra(hafiz_id=auth)
    hafizs_items.xtra(hafiz_id=auth)


bware = Beforeware(before, skip=["/hafiz_selection", "/login", "/logout", "/add_hafiz"])

app, rt = fast_app(
    before=bware,
    hdrs=(Theme.blue.headers(), hyperscript_header, alpinejs_header),
    bodykw={"hx-boost": "true"},
)


def get_item_id(page_number: int, not_memorized_only: bool = False):
    """
    This function will lookup the page_number in the `hafizs_items` table
    if there is no record for that page and then create new records for that page
    by looking up the `items` table

    Each page may contain more than one record (including the page_part)

    Then filter out the in_active hafizs_items and return the item_id

    Returns:
    list of item_id
    """

    qry = f"page_number = {page_number}"
    hafiz_data = hafizs_items(where=qry)

    if not hafiz_data:
        page_items = items(where=f"page_id = {page_number} AND active = 1")
        for item in page_items:
            hafizs_items.insert(
                Hafiz_Items(
                    item_id=item.id,
                    page_number=item.page_id,
                    mode_id=1,
                    # active=True,
                )
            )
    hafiz_data = (
        hafizs_items(
            where=f"{qry} AND status IS NULL"
        )  # Filter out memorized, as of now status is NULL
        if not_memorized_only
        else hafizs_items(where=qry)
    )
    item_ids = [
        hafiz_item.item_id
        for hafiz_item in hafiz_data
        if items[hafiz_item.item_id].active
    ]
    return item_ids


def get_column_headers(table):
    data_class = tables[table].dataclass()
    columns = [k for k in data_class.__dict__.keys() if not k.startswith("_")]
    return columns


def get_juz_name(page_id=None, item_id=None):
    if item_id:
        qry = f"SELECT pages.juz_number FROM pages LEFT JOIN items ON pages.id = items.page_id WHERE items.id = {item_id}"
        juz_number = db.q(qry)[0]["juz_number"]
    else:
        juz_number = pages[page_id].juz_number
    return juz_number


def get_surah_name(page_id=None, item_id=None):
    if item_id:
        surah_id = items[item_id].surah_id
    else:
        surah_id = items(where=f"page_id = {page_id}")[0].surah_id
    surah_details = surahs[surah_id]
    return surah_details.name


def mode_dropdown(default_mode=1, **kwargs):
    def mk_options(mode):
        id, name = mode.id, mode.name
        is_selected = lambda m: m == default_mode
        return Option(name, value=id, selected=is_selected(id))

    return LabelSelect(
        map(mk_options, modes()),
        label="Mode Id",
        name="mode_id",
        select_kwargs={"name": "mode_id"},
        **kwargs,
    )


def action_buttons(last_added_page=1, source="Home"):

    if isinstance(last_added_page, int):
        last_added_page += 1
    entry_buttons = Form(
        DivLAligned(
            Input(
                type="text",
                placeholder="page",
                cls="max-w-12 sm:max-w-16",
                id="page",
                value=last_added_page,
                autocomplete="off",
                required=True,
            ),
            Button("Bulk Entry", name="type", value="bulk", cls=ButtonT.link),
            Button("Single Entry", name="type", value="single", cls=ButtonT.link),
            cls=("gap-3", FlexT.wrap),
        ),
        action="/revision/entry",
        method="POST",
    )
    # Enable and Disable the button based on the checkbox selection
    dynamic_enable_button_hyperscript = "on checkboxChanged if first <input[type=checkbox]:checked/> remove @disabled else add @disabled"
    import_export_buttons = DivLAligned(
        Button(
            "Bulk Edit",
            hx_post="/revision/bulk_edit",
            hx_push_url="true",
            hx_include="closest form",
            hx_target="body",
            cls="toggle_btn",  # To disable and enable the button based on the checkboxes (Don't change, it is referenced in hyperscript)
            disabled=True,
            _=dynamic_enable_button_hyperscript,
        ),
        Button(
            "Bulk Delete",
            hx_delete="/revision",
            hx_confirm="Are you sure you want to delete these revisions?",
            hx_target="body",
            cls=("toggle_btn", ButtonT.destructive),
            disabled=True,
            _=dynamic_enable_button_hyperscript,
        ),
        A(
            Button("Export", type="button"),
            href="tables/revisions/export",
            hx_boost="false",
        ),
    )
    return DivFullySpaced(
        entry_buttons if source == "Home" else Div(),
        import_export_buttons if source == "Revision" else Div(),
        cls="flex-wrap gap-4 mb-3",
    )


def split_page_range(page_range: str):
    start_id, end_id = (
        page_range.split("-") if "-" in page_range else [page_range, None]
    )
    start_id = int(start_id)
    end_id = int(end_id) if end_id else None
    return start_id, end_id


def datewise_summary_table(show=None, hafiz_id=None):
    qry = f"SELECT MIN(revision_date) AS earliest_date FROM {revisions}"
    qry = (qry + f" WHERE hafiz_id = {hafiz_id}") if hafiz_id else qry
    result = db.q(qry)
    earliest_date = result[0]["earliest_date"]
    current_date = current_time("%Y-%m-%d")

    date_range = pd.date_range(
        start=(earliest_date or current_date), end=current_date, freq="D"
    )
    date_range = [date.strftime("%Y-%m-%d") for date in date_range][::-1]
    date_range = date_range[:show] if show else date_range

    def _render_datewise_row(date):
        # Get the unique modes for that particular date
        rev_condition = f"WHERE revisions.revision_date = '{date}'" + (
            f" AND revisions.hafiz_id = {hafiz_id}" if hafiz_id else ""
        )
        unique_modes = db.q(f"SELECT DISTINCT mode_id FROM {revisions} {rev_condition}")
        unique_modes = sorted([m["mode_id"] for m in unique_modes])

        mode_with_ids_and_pages = []
        for mode_id in unique_modes:
            # Joining the revisions and items table to get these columns
            # rev_id(Ids are needed for bulk_edit),
            # items_id(To correctly render the surah name if its starts from part),
            # page_id(To group pages into range)
            rev_query = f"SELECT revisions.id, revisions.item_id, items.page_id FROM {revisions} LEFT JOIN {items} ON revisions.item_id = items.id {rev_condition} AND mode_id = {mode_id}"
            current_date_and_mode_revisions = db.q(rev_query)
            mode_with_ids_and_pages.append(
                {
                    "mode_id": mode_id,
                    "revision_data": current_date_and_mode_revisions,
                }
            )

        def _render_pages_range(revisions_data: list):
            page_ranges = compact_format(sorted([r["page_id"] for r in revisions_data]))

            # get the surah name using the item_id for the corresponding page
            def _render_page(page):
                item_id = [
                    r["item_id"] for r in revisions_data if r["page_id"] == page
                ][0]
                return Span(
                    Span(page, cls=TextPresets.bold_sm),
                    f" - {get_surah_name(item_id=item_id)}",
                )

            # This function will return the list of rev_id based on max and min page for bulk_edit url
            def get_ids_for_page_range(data, min_page, max_page=None):
                result = []
                # Filter based on page_id values
                for item in data:
                    page_id = item["page_id"]
                    if max_page is None:
                        if page_id == min_page:
                            result.append(item["id"])
                    else:
                        if min_page <= page_id <= max_page:
                            result.append(item["id"])
                # Sort the result and convert them into str
                return list(map(str, sorted(result)))

            ctn = []
            for page_range in page_ranges.split(","):
                start_page, end_page = split_page_range(page_range)
                if end_page:
                    range_desc = (
                        _render_page(start_page),
                        Span(" -> "),
                        _render_page(end_page),
                    )
                else:
                    range_desc = _render_page(start_page)

                ctn.append(
                    Span(
                        A(
                            *range_desc,
                            hx_get=f"/revision/bulk_edit?ids={','.join(get_ids_for_page_range(revisions_data, start_page, end_page))}",
                            hx_push_url="true",
                            hx_target="body",
                            cls=(AT.classic),
                        ),
                        cls="block",
                    )
                )

            return P(
                *ctn,
                cls="space-y-3",
            )

        # To handle if the date has no entry
        if not mode_with_ids_and_pages:
            return [
                Tr(
                    Td(date_to_human_readable(date)),
                    Td("-"),
                    Td("-"),
                    Td("-"),
                )
            ]

        rows = [
            Tr(
                (
                    # Only add the date for the first row and use rowspan to expand them for the modes breakdown
                    Td(
                        date_to_human_readable(date),
                        rowspan=f"{len(mode_with_ids_and_pages)}",
                    )
                    if mode_with_ids_and_pages[0]["mode_id"] == o["mode_id"]
                    else None
                ),
                Td(modes[o["mode_id"]].name),
                Td(len(o["revision_data"])),
                Td(_render_pages_range(o["revision_data"])),
            )
            for o in mode_with_ids_and_pages
        ]
        return rows

    datewise_table = Div(
        Table(
            Thead(Tr(Th("Date"), Th("Mode"), Th("Count"), Th("Range"))),
            Tbody(*flatten_list(map(_render_datewise_row, date_range))),
        ),
        cls="uk-overflow-auto",
    )
    return datewise_table


def render_hafiz_card(hafizs_user, auth):
    is_current_hafizs_user = auth != hafizs_user.hafiz_id
    return Card(
        (
            Subtitle("last 3 revision")(
                datewise_summary_table(show=3, hafiz_id=hafizs_user.hafiz_id)
            ),
        ),
        header=DivFullySpaced(H3(hafizs[hafizs_user.hafiz_id].name)),
        footer=Button(
            "Switch hafiz" if is_current_hafizs_user else "Go to home",
            name="current_hafiz_id",
            value=hafizs_user.hafiz_id,
            hx_post="/hafiz_selection",
            hx_target="body",
            hx_replace_url="true",
            id=f"btn-{hafizs[hafizs_user.hafiz_id].name}",
            cls=(ButtonT.primary if is_current_hafizs_user else ButtonT.secondary),
        ),
        cls="min-w-[300px] max-w-[400px]",
    )


def render_options(option):
    return Option(
        option.capitalize(),
        value=option,
    )


login_redir = RedirectResponse("/login", status_code=303)


@app.get("/login")
def login():
    form = Form(
        LabelInput(label="Email", name="email", type="email"),
        LabelInput(label="Password", name="password", type="password"),
        Button("Login"),
        action="/login",
        method="post",
    )
    return Titled("Login", form)


@dataclass
class Login:
    email: str
    password: str


@app.post("/login")
def login_post(login: Login, sess):
    if not login.email or not login.password:
        return login_redir
    try:
        u = users(where="email = '{}'".format(login.email))[0]
    except IndexError:
        # u = users.insert(login)
        return login_redir
    if not compare_digest(u.password.encode("utf-8"), login.password.encode("utf-8")):
        return login_redir
    sess["user_auth"] = u.id
    hafizs_users.xtra(id=u.id)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(sess):
    user_auth = sess.get("user_auth", None)
    if user_auth is not None:
        del sess["user_auth"]
    auth = sess.get("auth", None)
    if auth is not None:
        del sess["auth"]
    return RedirectResponse("/login", status_code=303)


@app.post("/add_hafiz")
def add_hafiz_and_relations(hafiz: Hafiz, relationship: str, sess):
    hafiz_id = hafizs.insert(hafiz)
    hafizs_users.insert(
        hafiz_id=hafiz_id.id,
        user_id=sess["user_auth"],
        relationship=relationship,
        granted_by_user_id=sess["user_auth"],
        granted_at=datetime.now().strftime("%d-%m-%y %H:%M:%S"),
    )
    return RedirectResponse("/hafiz_selection", status_code=303)


@app.get("/hafiz_selection")
def hafiz_selection(sess):
    # In beforeware we are adding the hafiz_id filter using xtra
    # we have to reset that xtra attribute in order to show revisions for all hafiz
    revisions.xtra()
    hafizs_users.xtra()
    auth = sess.get("auth", None)
    user_auth = sess.get("user_auth", None)
    if user_auth is None:
        return login_redir

    # cards = [render_hafiz_card(h, auth) for h in hafizs()]
    cards = [
        render_hafiz_card(h, auth) for h in hafizs_users() if h.user_id == user_auth
    ]
    hafiz_form = Card(
        Titled(
            "Add Hafiz",
            Form(
                LabelInput(label="Hafiz Name", name="name", required=True),
                LabelSelect(
                    *map(render_options, OPTION_MAP["age_group"]),
                    label="Age Group",
                    name="age_group",
                ),
                LabelInput(
                    label="Daily Capacity",
                    name="daily_capacity",
                    type="number",
                    min="1",
                    value="1",
                    required=True,
                ),
                LabelSelect(
                    *map(render_options, OPTION_MAP["relationship"]),
                    label="Relationship",
                    name="relationship",
                ),
                Button("Add Hafiz"),
                action="/add_hafiz",
                method="post",
                cls="space-y-3",
            ),
        ),
        cls="w-[300px]",
    )
    return main_area(
        H5("Select Hafiz"),
        Div(*cards, cls=(FlexT.block, FlexT.wrap, "gap-4")),
        Div(hafiz_form),
        auth=auth,
    )


@app.post("/hafiz_selection")
def change_hafiz(current_hafiz_id: int, sess):
    sess["auth"] = current_hafiz_id
    return RedirectResponse("/", status_code=303)


def main_area(*args, active=None, auth=None):
    is_active = lambda x: AT.primary if x == active else None
    title = A("Quran SRS", href=index)
    hafiz_name = A(
        f"{hafizs[auth].name if auth is not None else "Select hafiz"}",
        href="/hafiz_selection",
        method="GET",
    )
    return Title("Quran SRS"), Container(
        Div(
            NavBar(
                A("Home", href=index, cls=is_active("Home")),
                A("Revision", href=revision, cls=is_active("Revision")),
                A(
                    "Memorization Status",
                    href="/memorization_status/juz",
                    cls=is_active("Memorization Status"),
                ),
                A(
                    "New Memorization",
                    href="/new_memorization/juz",
                    cls=is_active("New Memorization"),
                ),
                A("Tables", href="/tables", cls=is_active("Tables")),
                A("logout", href="/logout"),
                # A("User", href=user, cls=is_active("User")), # The user nav is temporarily disabled
                brand=H3(title, Span(" - "), hafiz_name),
            ),
            DividerLine(y_space=0),
            cls="bg-white sticky top-0 z-10",
        ),
        Main(*args, cls="p-4", id="main") if args else None,
        cls=ContainerT.xl,
    )


def tables_main_area(*args, active_table=None, auth=None):
    is_active = lambda x: "uk-active" if x == active_table else None

    tables_list = [
        t for t in str(tables).split(", ") if not t.startswith(("sqlite", "_"))
    ]
    table_links = [
        Li(A(t.capitalize(), href=f"/tables/{t}"), cls=is_active(t))
        for t in tables_list
    ]

    side_nav = NavContainer(
        NavParentLi(
            H4("Tables", cls="pl-4"),
            NavContainer(*table_links, parent=False),
        )
    )

    return main_area(
        Div(
            Div(side_nav, cls="flex-1 p-2"),
            (
                Div(*args, cls="flex-[4] border-l-2 p-4", id="table_view")
                if args
                else None
            ),
            cls=(FlexT.block, FlexT.wrap),
        ),
        active="Tables",
        auth=auth,
    )


@rt
def index(auth):
    revision_data = revisions()
    last_added_item_id = revision_data[-1].item_id if revision_data else None

    if last_added_item_id:
        item_details = items[last_added_item_id]
        last_added_page = item_details.page_id

        if item_details.item_type == "page-part":
            # fill the page input with parts based on the last added record
            # to start from the next part
            if "1" in item_details.part:
                last_added_page = last_added_page + 0.2
            elif (
                len(items(where=f"page_id = {last_added_page} AND active != 0")) > 2
                and "2" in item_details.part
            ):
                last_added_page = last_added_page + 0.3
    else:
        last_added_page = None

    # if it is greater than 604, we are reseting the last added page to None
    if isinstance(last_added_page, int) and last_added_page >= 604:
        last_added_page = None

    ################### Overall summary ###################
    # Sequential revision table
    seq_id = "1"
    qry = f"SELECT plan_id FROM {revisions} WHERE mode_id = {seq_id} ORDER BY revision_date DESC"
    result = db.q(qry)
    seq_plan_ids = [i["plan_id"] for i in result]
    # when using the `DISTINCT` keyword in the query the original order of the rows is not preserved
    # so we need to use the `dict.fromkeys` method to remove the duplicates which preserves the order
    unique_seq_plan_id = list(dict.fromkeys(seq_plan_ids))
    # To get the unique page ranges for the plan_id
    unique_page_ranges = []
    for plan_id in unique_seq_plan_id:
        if not plan_id:
            continue
        pages_list = sorted(
            [
                items[r.item_id].page_id
                for r in revisions(
                    where=f"mode_id = '{seq_id}' AND plan_id = '{plan_id}'"
                )
            ]
        )
        # If the plan is completed then we are not showing the gaps (such as showing them in diff rows)
        # instead we'll show the start and end page of the plan
        if plans[plan_id].completed and pages_list:
            unique_page_ranges.append(
                {"plan_id": plan_id, "page_range": f"{pages_list[0]}-{pages_list[-1]}"}
            )
            continue

        for p in compact_format(pages_list).split(", "):
            unique_page_ranges.append({"plan_id": plan_id, "page_range": p})

    def render_overall_row(o: dict):
        def render_page(page):
            return Span(
                Span(page, cls=TextPresets.bold_sm),
                f" - {get_surah_name(page_id=page)}",
            )

        plan_id, page_range = o["plan_id"], o["page_range"]
        if not page_range:
            return None

        start_page, end_page = split_page_range(page_range)
        next_page = (end_page or start_page) + 1

        current_plan = plans(where=f"id = '{plan_id}'")
        if current_plan:
            is_completed = current_plan[0].completed
        else:
            is_completed = False

        if is_completed:
            continue_message = "Completed"
        elif next_page > 604:
            continue_message = "No further page"
        else:
            continue_message = A(
                render_page(next_page),
                href=f"revision/bulk_add?page={next_page}&mode_id={seq_id}&plan_id={plan_id}",
                cls=AT.classic,
            )

        return Tr(
            Td(A(plan_id, href=f"/tables/plans/{plan_id}/edit", cls=AT.muted)),
            Td(page_range),
            Td(render_page(start_page)),
            (Td(render_page(end_page) if end_page else None)),
            Td(continue_message),
        )

    overall_table = Div(
        H4("Sequential Revision Round"),
        Table(
            Thead(
                Tr(
                    Th("Plan Id"),
                    Th("Range"),
                    Th("Start"),
                    Th("End"),
                    Th("Continue"),
                )
            ),
            Tbody(*map(render_overall_row, unique_page_ranges)),
        ),
        cls="uk-overflow-auto",
    )

    return main_area(
        action_buttons(
            **(
                {"last_added_page": last_added_page}
                if last_added_page is not None
                else {}
            )
        ),
        Div(overall_table, Divider(), datewise_summary_table(hafiz_id=auth)),
        active="Home",
        auth=auth,
    )


@app.get("/tables")
def list_tables(auth):
    return tables_main_area(auth=auth)


@app.get("/tables/{table}")
def view_table(table: str, auth):
    records = db.q(f"SELECT * FROM {table}")
    columns = get_column_headers(table)

    def _render_rows(data: dict):
        def render_cell(column: str):
            if column == "id":
                return Td(
                    A(
                        data[column],
                        href=f"/tables/{table}/{data[column]}/edit",
                        cls=AT.muted,
                    )
                )
            return Td(data[column])

        return Tr(
            *map(render_cell, columns),
            Td(
                A(
                    "Delete",
                    hx_delete=f"/tables/{table}/{data["id"]}",
                    target_id=f"row-{data["id"]}",
                    hx_swap="outerHTML",
                    hx_confirm="Are you sure?",
                    cls=AT.muted,
                ),
            ),
            id=f"row-{data["id"]}",
        )

    table_element = Table(
        Thead(Tr(*map(Th, columns), Th("Action"))),
        Tbody(*map(_render_rows, records)),
    )
    return tables_main_area(
        Div(
            DivFullySpaced(
                DivLAligned(
                    A(
                        UkIcon("undo-2", height=15, width=15),
                        cls="px-6 py-3 shadow-md rounded-sm",
                        href=f"/tables",
                    ),
                    A(
                        Button("New", type="button", cls=ButtonT.link),
                        href=f"/tables/{table}/new",
                    ),
                ),
                DivRAligned(
                    A(
                        Button("Export", type="button", cls=ButtonT.link),
                        href=f"/tables/{table}/export",
                        hx_boost="false",
                    ),
                    A(
                        Button("Import", type="button", cls=ButtonT.link),
                        href=f"/tables/{table}/import",
                    ),
                ),
            ),
            Div(table_element, cls="uk-overflow-auto"),
            cls="space-y-3",
        ),
        active_table=table,
        auth=auth,
    )


def create_dynamic_input_form(schema: dict, **kwargs):
    input_types_map = {"int": "number", "str": "text", "date": "date"}

    def create_input_field(o: dict):
        column, datatype = o
        if column == "id":
            return None
        # datatype is an union type, so we need to extract the first element using __args__
        # and it returns datatype class so to get the name we'll use __name__ attribute
        datatype = datatype.__args__[0].__name__
        input_type = input_types_map.get(datatype, "text")
        # The datatype for the date column are stored in str
        # so we are checking if the 'date'  is in the column name
        if "date" in column:
            input_type = "date"
        # The bool datatype is stored in int
        # so we are creating a column list that are bool to compare against column name
        if column in ["completed"]:
            return Div(
                FormLabel(column),
                LabelRadio(label="True", id=f"{column}-1", name=column, value="1"),
                LabelRadio(label="False", id=f"{column}-2", name=column, value="0"),
                cls="space-y-2",
            )
        if column in ["role", "age_group", "relationship"]:
            return (
                LabelSelect(
                    *map(render_options, OPTION_MAP[column]),
                    label=column.capitalize(),
                    name=column,
                ),
            )
        return LabelInput(column, type=input_type)

    return Form(
        *map(create_input_field, schema.items()),
        DivFullySpaced(
            Button("Save"),
            A(Button("Discard", type="button"), onclick="history.back()"),
        ),
        **kwargs,
        cls="space-y-4",
    )


@app.get("/tables/{table}/{record_id}/edit")
def edit_record_view(table: str, record_id: int, auth):
    current_table = tables[table]
    current_data = current_table[record_id]

    # The completed column is stored in int and it is considered as bool
    # so we are converting it to str in order to select the right radio button using fill_form
    if table == "plans":
        current_data.completed = str(current_data.completed)

    column_with_types = get_column_and_its_type(table)
    form = create_dynamic_input_form(
        column_with_types, hx_put=f"/tables/{table}/{record_id}"
    )

    return tables_main_area(
        Titled(f"Edit page", fill_form(form, current_data)),
        active_table=table,
        auth=auth,
    )


def get_column_and_its_type(table):
    data_class = tables[table].dataclass()
    return data_class.__dict__["__annotations__"]


@app.put("/tables/{table}/{record_id}")
async def update_record(table: str, record_id: int, req: Request):
    formt_data = await req.form()
    current_data = formt_data.__dict__.get("_dict")
    # remove the key if the value is empty
    current_data = {key: value for key, value in current_data.items() if value != ""}
    tables[table].update(current_data, record_id)

    return Redirect(f"/tables/{table}")


@app.delete("/tables/{table}/{record_id}")
def delete_record(table: str, record_id: int):
    try:
        tables[table].delete(record_id)
    except Exception as e:
        return Tr(Td(P(f"Error: {e}"), colspan="11", cls="text-center"))


@app.get("/tables/{table}/new")
def new_record_view(table: str, auth):
    column_with_types = get_column_and_its_type(table)
    return tables_main_area(
        Titled(
            f"Add page",
            create_dynamic_input_form(column_with_types, hx_post=f"/tables/{table}"),
        ),
        active_table=table,
        auth=auth,
    )


@app.post("/tables/{table}")
async def create_new_record(table: str, req: Request):
    formt_data = await req.form()
    current_data = formt_data.__dict__.get("_dict")
    tables[table].insert(current_data)
    return Redirect(f"/tables/{table}")


@app.get("/tables/{table}/export")
def export_specific_table(table: str):
    df = pd.DataFrame(tables[table]())

    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    # file_name = f"{table}_{current_time("%Y%m%d%I%M")}"
    file_name = f"{table}.csv"
    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@app.get("/tables/{table}/import")
def import_specific_table_view(table: str):
    form = Form(
        UploadZone(
            DivCentered(Span("Upload Zone"), UkIcon("upload")),
            id="file",
            accept="text/csv",
        ),
        DivFullySpaced(
            Button("Submit"),
            Button(
                "Preview",
                type="button",
                hx_post=f"/tables/{table}/import/preview",
                hx_include="#file",
                hx_encoding="multipart/form-data",
                target_id="preview_table",
                hx_push_url="false",
            ),
            Button("Cancel", type="button", onclick="history.back()"),
        ),
        action=f"/tables/{table}/import",
        method="POST",
    )
    return tables_main_area(
        Titled(
            f"Upload CSV",
            P(
                f"CSV should contain only these columns: ",
                Span(
                    " ,".join(get_column_headers(table)), cls=TextPresets.md_weight_sm
                ),
            ),
            form,
            Div(id="preview_table"),
            cls="space-y-4",
        ),
        active_table=table,
    )


@app.post("/tables/{table}/import/preview")
async def import_specific_table_preview(table: str, file: UploadFile):
    file_content = await file.read()
    imported_df = pd.read_csv(BytesIO(file_content)).fillna("")
    columns = imported_df.columns.tolist()
    records = imported_df.to_dict(orient="records")

    # Check if the columns match the table's columns
    if sorted(columns) != sorted(get_column_headers(table)):
        return Div(
            H3("Filename: ", file.filename),
            P("Please check the columns in the CSV file", cls="text-red-500"),
        )

    def _render_rows(data: dict):
        return Tr(
            *map(lambda col: Td(data[col]), columns),
        )

    preview_table = Table(
        Thead(Tr(*map(Th, columns))),
        Tbody(*map(_render_rows, records)),
    )
    return Div(H3("Filename: ", file.filename), Div(preview_table))


@app.post("/tables/{table}/import")
async def import_specific_table(table: str, file: UploadFile):
    backup_sqlite_db(DB_PATH, "data/backup")
    # Instead of using the import_file method, we are using upsert method to import the csv file
    # as some of the forign key values are being used in another table
    # so we cannot truncate the table
    file_content = await file.read()
    data = pd.read_csv(BytesIO(file_content)).to_dict("records")
    for record in data:
        tables[table].upsert(record)

    return Redirect(f"/tables/{table}")


# this function is used to create infinite scroll for the revisions table
def generate_revision_table_part(part_num: int = 1, size: int = 20) -> Tuple[Tr]:
    start = (part_num - 1) * size
    end = start + size
    data = revisions(order_by="id desc")[start:end]

    def _render_rows(rev: Revision):
        item_id = rev.item_id
        item_details = items[item_id]
        page = item_details.page_id
        return Tr(
            # Td(rev.id),
            # Td(rev.user_id),
            Td(
                CheckboxX(
                    name="ids",
                    value=rev.id,
                    cls="revision_ids",
                    # To trigger the checkboxChanged event to the bulk edit and bulk delete buttons
                    _="on click send checkboxChanged to .toggle_btn",
                    _at_click="handleCheckboxClick($event)",
                )
            ),
            Td(
                A(
                    page,
                    href=f"/revision/edit/{rev.id}",
                    cls=AT.muted,
                )
            ),
            # FIXME: Added temporarly to check is the date is added correctly and need to remove this
            Td(item_details.part),
            Td(rev.mode_id),
            Td(rev.plan_id),
            Td(RATING_MAP.get(str(rev.rating))),
            Td(get_surah_name(item_id=item_id)),
            Td(pages[page].juz_number),
            Td(rev.revision_date),
            Td(
                A(
                    "Delete",
                    hx_delete=f"/revision/delete/{rev.id}",
                    target_id=f"revision-{rev.id}",
                    hx_swap="outerHTML",
                    hx_confirm="Are you sure?",
                    cls=AT.muted,
                ),
            ),
            id=f"revision-{rev.id}",
        )

    paginated = [_render_rows(i) for i in data]

    if len(paginated) == 20:
        paginated[-1].attrs.update(
            {
                "get": f"revision?idx={part_num + 1}",
                "hx-trigger": "revealed",
                "hx-swap": "afterend",
                "hx-select": "tbody > tr",
            }
        )
    return tuple(paginated)


@app.get
def revision(auth, idx: int | None = 1):
    table = Table(
        Thead(
            Tr(
                # Columns are temporarily hidden
                # Th("Id"),
                # Th("User Id"),
                Th(),  # empty header for checkbox
                Th("Page"),
                Th("Part"),
                # FIXME: Added temporarly to check is the date is added correctly and need to remove this
                Th("Mode"),
                Th("Plan Id"),
                Th("Rating"),
                Th("Surah"),
                Th("Juz"),
                Th("Revision Date"),
                Th("Action"),
            )
        ),
        Tbody(*generate_revision_table_part(part_num=idx)),
        x_data=select_all_checkbox_x_data(class_name="revision_ids"),
    )
    return main_area(
        # To send the selected revision ids for bulk delete and bulk edit
        Form(
            action_buttons(source="Revision"),
            Div(table, cls="uk-overflow-auto"),
        ),
        active="Revision",
        auth=auth,
    )


# This function is to hide the id fields with toggle button
def toggle_input_fields(*args, show_id_fields=False):
    return (
        Div(
            LabelSwitch(
                label="Show additional fields", id="show_id_fields", x_model="isChecked"
            ),
            Grid(
                *args,
                cols=2,
                cls=("gap-4", "hidden" if not show_id_fields else None),
                **{"x-bind:class": "{ 'hidden': !isChecked }"},
            ),
            x_data="{ isChecked: IS_HIDE_FIELDS }".replace(
                "IS_HIDE_FIELDS", "true" if show_id_fields else "false"
            ),
            cls="space-y-3",
        ),
    )


def create_revision_form(type, show_id_fields=False):
    def RadioLabel(o):
        value, label = o
        is_checked = True if value == "1" else False
        return Div(
            FormLabel(
                Radio(
                    id="rating", value=value, checked=is_checked, autofocus=is_checked
                ),
                Span(label),
                cls="space-x-2",
            )
        )

    def _option(obj):
        return Option(
            f"{obj.id} ({obj.name})",
            value=obj.id,
            # TODO: Temp condition for selecting siraj, later it should be handled by sess
            # Another caviat is that siraj should be in the top of the list of users
            # or else the edit functionality will not work properly.
            selected=True if "siraj" in obj.name.lower() else False,
        )

    additional_fields = (
        mode_dropdown(),
        LabelInput("Plan Id", name="plan_id", type="number"),
        LabelInput(
            "Revision Date",
            name="revision_date",
            type="date",
            value=current_time("%Y-%m-%d"),
            cls="space-y-2 col-span-2",
        ),
    )

    return Form(
        Hidden(name="id"),
        # Hide the User selection temporarily
        LabelSelect(
            *map(_option, hafizs()), label="Hafiz Id", name="hafiz_id", cls="hidden"
        ),
        (
            toggle_input_fields(*additional_fields, show_id_fields=show_id_fields)
            if type == "add"
            else Grid(*additional_fields)
        ),
        LabelInput("Page", name="page_no", type="number", input_cls="text-2xl"),
        Div(
            FormLabel("Rating"),
            *map(RadioLabel, RATING_MAP.items()),
            cls="space-y-2 leading-8 sm:leading-6 ",
        ),
        Div(
            Button("Save", cls=ButtonT.primary),
            A(Button("Cancel", type="button", cls=ButtonT.secondary), href=index),
            cls="flex justify-around items-center w-full",
        ),
        action=f"/revision/{type}",
        method="POST",
    )


@rt("/revision/edit/{revision_id}")
def get(revision_id: int, auth):
    current_revision = revisions[revision_id].__dict__
    current_revision["page_no"] = items[current_revision["item_id"]].page_id
    # Convert rating to string in order to make the fill_form to select the option.
    current_revision["rating"] = str(current_revision["rating"])
    form = create_revision_form("edit")
    return main_area(
        Titled("Edit Revision", fill_form(form, current_revision)),
        active="Revision",
        auth=auth,
    )


@rt("/revision/edit")
def post(revision_details: Revision):
    # setting the plan_id to None if it is 0
    # as it get defaults to 0 if the field is empty.
    revision_details.plan_id = set_zero_to_none(revision_details.plan_id)
    revisions.update(revision_details)
    return Redirect(revision)


@rt("/revision/delete/{revision_id}")
def delete(revision_id: int):
    revisions.delete(revision_id)


@app.delete("/revision")
def revision_delete_all(ids: List[int]):
    for id in ids:
        revisions.delete(id)
    return RedirectResponse(revision, status_code=303)


# This is to handle the checkbox on revison page as it was coming as individual ids.
@app.post("/revision/bulk_edit")
def bulk_edit_redirect(ids: List[str]):
    return RedirectResponse(f"/revision/bulk_edit?ids={','.join(ids)}", status_code=303)


@app.get("/revision/bulk_edit")
def bulk_edit_view(ids: str, auth):
    ids = ids.split(",")

    # Get the default values from the first selected revision
    first_revision = revisions[ids[0]]

    def _render_row(id):
        current_revision = revisions[id]

        def _render_radio(o):
            value, label = o

            is_checked = True if int(value) == current_revision.rating else False
            return FormLabel(
                Radio(name=f"rating-{id}", value=value, checked=is_checked),
                Span(label),
                cls="space-x-2",
            )

        item_details = items[current_revision.item_id]
        return Tr(
            Td(
                CheckboxX(
                    name="ids",
                    value=id,
                    cls="revision_ids",
                    # _at_ is a alias for @
                    _at_click="handleCheckboxClick($event)",  # To handle `shift+click` selection
                )
            ),
            Td(P(item_details.surah_name)),
            Td(P(item_details.page_id)),
            Td(P(item_details.part)),
            Td(P(item_details.start_text)),
            Td(P(current_revision.revision_date)),
            Td(P(current_revision.mode_id)),
            Td(P(current_revision.plan_id)),
            Td(
                Div(
                    *map(_render_radio, RATING_MAP.items()),
                    cls=(FlexT.block, FlexT.row, FlexT.wrap, "gap-x-6 gap-y-4"),
                )
            ),
        )

    table = Table(
        Thead(
            Tr(
                Th(
                    CheckboxX(
                        cls="select_all",
                        x_model="selectAll",  # To update the current status of the checkbox (checked or unchecked)
                        _at_change="toggleAll()",  # based on that update the status of all the checkboxes
                    )
                ),
                Th("Surah"),
                Th("Page"),
                Th("Part"),
                Th("Start"),
                Th("Date"),
                Th("Mode"),
                Th("Plan ID"),
                Th("Rating"),
            )
        ),
        Tbody(*[_render_row(i) for i in ids]),
        # defining the reactive data for for component to reference (alpine.js)
        x_data=select_all_checkbox_x_data(class_name="revision_ids"),
        # initializing the toggleAll function to select all the checkboxes by default.
        x_init="toggleAll()",
    )

    action_buttons = Div(
        Button("Save", cls=ButtonT.primary),
        Button(
            "Cancel", type="button", cls=ButtonT.secondary, onclick="history.back()"
        ),
        cls=(FlexT.block, FlexT.around, FlexT.middle, "w-full"),
    )

    return main_area(
        H1("Bulk Edit Revision"),
        Form(
            Grid(
                mode_dropdown(default_mode=first_revision.mode_id),
                LabelInput(
                    "Plan ID",
                    name="plan_id",
                    type="number",
                    value=first_revision.plan_id,
                ),
            ),
            Div(
                LabelInput(
                    "Revision Date",
                    name="revision_date",
                    type="date",
                    value=first_revision.revision_date,
                    cls="space-y-2 w-full",
                ),
                Button(
                    "Delete",
                    hx_delete="/revision",
                    hx_confirm="Are you sure you want to delete these revisions?",
                    hx_target="body",
                    hx_push_url="true",
                    cls=ButtonT.destructive,
                ),
                cls=(FlexT.block, FlexT.between, FlexT.bottom, "w-full gap-2"),
            ),
            Div(table, cls="uk-overflow-auto"),
            action_buttons,
            action="/revision",
            method="POST",
        ),
        active="Revision",
        auth=auth,
    )


@app.post("/revision")
async def bulk_edit_save(revision_date: str, mode_id: int, plan_id: int, req):
    plan_id = set_zero_to_none(plan_id)
    form_data = await req.form()
    ids_to_update = form_data.getlist("ids")

    for name, value in form_data.items():
        if name.startswith("rating-"):
            current_id = name.split("-")[1]
            if current_id in ids_to_update:
                revisions.update(
                    Revision(
                        id=int(current_id),
                        rating=int(value),
                        revision_date=revision_date,
                        mode_id=mode_id,
                        plan_id=plan_id,
                    )
                )

    return RedirectResponse("/revision", status_code=303)


# This route is used to redirect to the appropriate revision entry form
@rt("/revision/entry")
def post(type: str, page: str):
    if type == "bulk":
        return Redirect(f"/revision/bulk_add?page={page}")
    elif type == "single":
        return Redirect(f"/revision/add?page={page}")


@rt("/revision/add")
def get(
    auth, page: str, max_page: int = 605, date: str = None, show_id_fields: bool = False
):
    if "-" in page:
        page = page.split("-")[0]

    page_in_float = float(page)
    page = int(page_in_float)

    if page >= max_page:
        return Redirect(index)

    if len(get_item_id(page_number=int(page))) > 1:
        return Redirect(f"/revision/bulk_add?page={page}&is_part=1")

    try:
        last_added_record = revisions()[-1]
    except IndexError:
        defalut_mode_value = 1
        defalut_plan_value = None
    else:
        defalut_mode_value = last_added_record.mode_id
        defalut_plan_value = last_added_record.plan_id

    return main_area(
        Titled(
            f"{page} - {get_surah_name(page_id=page)} - {pages[page].start_text}",
            fill_form(
                create_revision_form("add", show_id_fields=show_id_fields),
                {
                    "page_no": page,
                    "mode_id": defalut_mode_value,
                    "plan_id": defalut_plan_value,
                    "revision_date": date,
                },
            ),
        ),
        active="Revision",
        auth=auth,
    )


@rt("/revision/add")
def post(page_no: int, revision_details: Revision, show_id_fields: bool = False):
    # The id is set to zero in the form, so we need to delete it
    # before inserting to generate the id automatically
    del revision_details.id
    revision_details.plan_id = set_zero_to_none(revision_details.plan_id)

    item_id = items(where=f"page_id = {page_no}")[0].id
    revision_details.item_id = item_id

    # updating the status of the item to memorized
    hafizs_items_id = hafizs_items(where=f"item_id = {item_id}")[0].id
    hafizs_items.update({"status": "memorized"}, hafizs_items_id)

    rev = revisions.insert(revision_details)

    return Redirect(
        f"/revision/add?page={page_no + 1}&date={rev.revision_date}&show_id_fields={show_id_fields}"
    )


# Bulk add
@app.get("/revision/bulk_add")
def get(
    auth,
    page: str,
    # is_part is to determine whether it came from single entry page or not
    is_part: bool = False,
    mode_id: int = None,
    plan_id: int = None,
    revision_date: str = None,
    length: int = 5,
    max_page: float = 604.4,
    show_id_fields: bool = False,
):

    # the length only matters if the pages have consecutive surahs
    if "-" in page:
        page, length = page.split("-")

    # Handle the max page
    if float(page) >= max_page:
        return Redirect(index)

    if "." in page:
        page, part = page.split(".")
        part = int(part)
    else:
        part = None

    page = int(page)
    length = int(length)

    # This is to show only one page if it came from single entry
    if is_part:
        length = 1

    last_page = page + length

    if last_page > max_page:
        last_page = math.ceil(max_page)

    item_ids = flatten_list(
        [get_item_id(page_number=p) for p in range(page, last_page)]
    )

    description = ""

    # if there is part in the page number,
    # then we need to slice them to exclude already added part
    if part:
        item_ids = item_ids[part - 1 :]

    if not is_part:

        # This will responsible for stopping the length on surah or juz end
        # TODO: currently we are not showing what is stopped like `juz end` or `surah end`
        _temp_item_ids = []
        first_page_surah = get_surah_name(item_id=item_ids[0])
        first_page_juz = get_juz_name(item_id=item_ids[0])

        for item_id in item_ids:
            current_surah = get_surah_name(item_id=item_id)
            current_juz = get_juz_name(item_id=item_id)

            if current_surah != first_page_surah and current_juz != first_page_juz:
                description = "Surah and Juz ends"
                break
            elif current_surah != first_page_surah:
                description = "Surah ends"
                break
            elif current_juz != first_page_juz:
                description = "Juz ends"
                break
            else:
                _temp_item_ids.append(item_id)

        if _temp_item_ids:
            item_ids = _temp_item_ids

    last_page = items[item_ids[-1]].page_id

    def _render_row(item_id):

        def _render_radio(o):
            value, label = o
            is_checked = True if value == "1" else False
            return FormLabel(
                Radio(
                    id=f"rating-{item_id}",
                    value=value,
                    checked=is_checked,
                    cls="toggleable-radio",
                ),
                Span(label),
                cls="space-x-2",
            )

        current_page_details = items[item_id]
        return Tr(
            Td(
                CheckboxX(
                    name="ids",
                    value=item_id,
                    cls="revision_ids",
                    _at_click="handleCheckboxClick($event)",
                )
            ),
            Td(P(current_page_details.page_id)),
            Td(current_page_details.part),
            Td(P(current_page_details.start_text, cls=(TextT.xl))),
            Td(
                Div(
                    *map(_render_radio, RATING_MAP.items()),
                    cls=(FlexT.block, FlexT.row, FlexT.wrap, "gap-x-6 gap-y-4"),
                )
            ),
        )

    table = Table(
        Thead(
            Tr(
                Th(
                    CheckboxX(
                        cls="select_all", x_model="selectAll", _at_change="toggleAll()"
                    )
                ),
                Th("Page"),
                Th("Part"),
                Th("Start"),
                Th("Rating"),
            )
        ),
        Tbody(
            *map(_render_row, item_ids),
            (
                Tr(Td(P(description), colspan="5", cls="text-center"))
                if description
                else None
            ),
        ),
        x_data=select_all_checkbox_x_data(
            class_name="revision_ids",
            is_select_all="false" if is_part else "true",
        ),
        x_init="toggleAll()",
    )

    action_buttons = Div(
        Button(
            "Save",
            cls=ButtonT.primary,
        ),
        A(Button("Cancel", type="button", cls=ButtonT.secondary), href=index),
        cls=(FlexT.block, FlexT.around, FlexT.middle, "w-full"),
    )

    try:
        last_added_record = revisions()[-1]
    except IndexError:
        defalut_mode_value = 1
        defalut_plan_value = None
    else:
        defalut_mode_value = last_added_record.mode_id
        defalut_plan_value = last_added_record.plan_id

    # if this page comes from single entry page, then we are displaying the all the surahs in that page
    if is_part:
        heading = f"{page} - " + ", ".join(
            [get_surah_name(item_id=item_id) for item_id in item_ids]
        )
    # if the bulk entry page shows only start page
    elif len(item_ids) == 1:
        heading = f"{page} - {get_surah_name(item_id=item_ids[-1])} - Juz {get_juz_name(item_id=item_ids[-1])}"
    else:
        heading = f"{page} => {last_page} - {get_surah_name(item_id=item_ids[-1])} - Juz {get_juz_name(item_id=item_ids[-1])}"

    return main_area(
        H1(heading),
        Form(
            Hidden(name="length", value=length),
            Hidden(name="is_part", value=str(is_part)),
            toggle_input_fields(
                mode_dropdown(default_mode=(mode_id or defalut_mode_value)),
                LabelInput(
                    "Plan ID",
                    name="plan_id",
                    type="number",
                    value=(plan_id or defalut_plan_value),
                ),
                LabelInput(
                    "Revision Date",
                    name="revision_date",
                    type="date",
                    value=(revision_date or current_time("%Y-%m-%d")),
                    cls="space-y-2 col-span-2",
                ),
                show_id_fields=show_id_fields,
            ),
            Div(table, cls="uk-overflow-auto"),
            action_buttons,
            action="/revision/bulk_add",
            method="POST",
        ),
        Script(src="/public/script.js"),
        active="Revision",
        auth=auth,
    )


@rt("/revision/bulk_add")
async def post(
    revision_date: str,
    mode_id: int,
    plan_id: int,
    length: int,
    is_part: bool,
    auth,
    req,
    show_id_fields: bool = False,
):
    plan_id = set_zero_to_none(plan_id)
    form_data = await req.form()
    item_ids = form_data.getlist("ids")

    parsed_data = []
    for name, value in form_data.items():
        if name.startswith("rating-"):
            item_id = name.split("-")[1]
            if item_id in item_ids:
                hafizs_items_id = hafizs_items(where=f"item_id = {item_id}")[0].id
                hafizs_items.update({"status": "memorized"}, hafizs_items_id)
                parsed_data.append(
                    Revision(
                        item_id=int(item_id),
                        rating=int(value),
                        hafiz_id=auth,
                        revision_date=revision_date,
                        mode_id=mode_id,
                        plan_id=plan_id,
                    )
                )

    revisions.insert_all(parsed_data)
    if parsed_data:
        last_item_id = parsed_data[-1].item_id
        # To show the next page
        last_page = items[last_item_id].page_id
    else:
        return Redirect(index)

    last_page_item_ids = get_item_id(last_page)

    if not last_page_item_ids:
        return Redirect(index)  # Handle the case where no items are found

    # if the last added page doesn't have part or it is the last part of that particular page
    # then add full page
    if len(last_page_item_ids) == 1 or last_item_id == last_page_item_ids[-1]:
        next_page = last_page + 1
    #  or if the page has parts then add decimal such as 604.2, 604.3
    else:
        next_page = f"{last_page}.{last_page_item_ids.index(last_item_id) + 2}"
        next_page = float(next_page)

    if is_part:
        return Redirect(
            f"/revision/add?page={math.ceil(next_page) if isinstance(next_page, float) else next_page  }&date={revision_date}"
        )

    return Redirect(
        f"/revision/bulk_add?page={next_page}&revision_date={revision_date}&length={length}&mode_id={mode_id}&plan_id={plan_id}&show_id_fields={show_id_fields}"
    )


@app.get("/memorization_status/{current_type}")
def show_page_status(current_type: str, auth, status: str = None):

    def render_row_based_on_type(type_number: str, records: list, current_type):
        memorized_status = [str(r["status"]).lower() == "memorized" for r in records]
        if all(memorized_status):
            status_value = "Memorized"
        elif any(memorized_status):
            status_value = "Partially Memorized"
        else:
            status_value = "Not Memorized"

        if status and status != standardize_column(status_value):
            return None

        _surahs = sorted({r["surah_id"] for r in records})
        _pages = sorted([r["page_number"] for r in records])
        _juzs = sorted({r["juz_number"] for r in records})

        def render_range(list, _type=""):
            first_description = list[0]
            last_description = list[-1]

            if _type == "Surah":
                _type = ""
                first_description = surahs[first_description].name
                last_description = surahs[last_description].name

            if len(list) == 1:
                return f"{_type} {first_description}"
            return f"{_type}{"" if _type == "" else "s"} {first_description} – {last_description}"

        surah_range = render_range(_surahs, "Surah")
        page_range = render_range(_pages, "Page")
        juz_range = render_range(_juzs, "Juz")

        if current_type == "juz":
            details = f"{surah_range} ({page_range})"
        elif current_type == "surah":
            details = f"{juz_range} ({page_range})"
        elif current_type == "page":
            details = f"{juz_range} | {surah_range}"

        title = (
            f"{current_type.capitalize()} {type_number}"
            if current_type != "surah"
            else surahs[type_number].name
        )
        return Tr(
            Td(title),
            Td(details),
            Td(status_value),
            Td(A("Update Status ➡️"), cls=(AT.classic, "text-right")),
            hx_get=f"/partial_memorization_status/{current_type}/{type_number}",
            hx_vals='{"title": "CURRENT_TITLE", "description": "CURRENT_DETAILS"}'.replace(
                "CURRENT_TITLE", title
            ).replace(
                "CURRENT_DETAILS", details
            ),
            target_id="my-modal-body",
            data_uk_toggle="target: #my-modal",
        )

    def group_by_type(data, current_type):
        columns_map = {
            "juz": "juz_number",
            "surah": "surah_id",
            "page": "page_number",
        }
        grouped = defaultdict(
            list
        )  # defaultdict() is creating the key as the each column_map number and value as the list of records
        for row in data:
            grouped[row[columns_map[current_type]]].append(row)
        return grouped

    if not current_type:
        current_type = "juz"

    def render_navigation_item(_type: str):
        return Li(
            A(
                f"by {_type}",
                href=f"/memorization_status/{_type}"
                + (f"?status={status}" if status else ""),
            ),
            cls=("uk-active" if _type == current_type else None),
        )

    qry = f"""SELECT items.id, items.surah_id, pages.page_number, pages.juz_number, hafizs_items.status FROM items 
                          LEFT JOIN pages ON items.page_id = pages.id
                          LEFT JOIN hafizs_items ON items.id = hafizs_items.item_id AND hafizs_items.hafiz_id = {auth}
                          WHERE items.active != 0;"""
    ct = db.q(qry)

    grouped = group_by_type(ct, current_type)
    rows = [
        render_row_based_on_type(type_number, records, current_type)
        for type_number, records in grouped.items()
    ]

    def render_filter_btn(text):
        return Label(
            text,
            hx_get=f"/memorization_status/{current_type}?status={standardize_column(text)}",
            hx_target="body",
            hx_push_url="true",
            cls=(
                "cursor-pointer",
                (
                    LabelT.primary
                    if status == standardize_column(text)
                    else LabelT.secondary
                ),
            ),
        )

    filter_btns = DivLAligned(
        P("Status Filter:", cls=TextPresets.muted_sm),
        *map(render_filter_btn, ["Memorized", "Not Memorized", "Partially Memorized"]),
        (
            Label(
                "X",
                hx_get=f"/memorization_status/{current_type}",
                hx_target="body",
                hx_push_url="true",
                cls=(
                    "cursor-pointer",
                    TextT.xs,
                    LabelT.destructive,
                    (None if status else "invisible"),
                ),
            )
        ),
    )

    # For memorization progress
    page_stats = defaultdict(lambda: {"memorized": 0, "total": 0})
    for item in ct:
        page = item["page_number"]
        page_stats[page]["total"] += 1
        if item["status"] == "memorized":
            page_stats[page]["memorized"] += 1

    total_memorized_pages = 0
    for page, stats in page_stats.items():
        total_memorized_pages += stats["memorized"] / stats["total"]

    # Is to get the total count of the type: ["juz", "surah", "page"]
    # to show stats below the progress bar
    def total_count(_type, _status):
        type_stats = group_by_type(ct, _type)
        count = 0
        for type_number, stats in type_stats.items():

            status_list = [item["status"] == "memorized" for item in stats]
            if _status == "memorized" and all(status_list):
                count += 1
            elif _status == "not_memorized" and not any(status_list):
                count += 1
            elif (
                _status == "partially_memorized"
                and any(status_list)
                and not all(status_list)
            ):
                count += 1
        return count

    type_with_total = {
        "juz": 30,
        "surah": 114,
        "page": 604,
    }

    def render_stat_row(_type):
        memorized_count = total_count(_type, "memorized")
        not_memorized_count = total_count(_type, "not_memorized")
        partially_memorized_count = total_count(_type, "partially_memorized")

        current_type_total = type_with_total[_type]
        count_percentage = lambda x: format_number(x / current_type_total * 100)

        def render_td(count):
            return Td(
                f"{count} ({count_percentage(count)}%)",
                cls="text-center",
            )

        return Tr(
            Th(destandardize_text(_type)),
            *map(
                render_td,
                [memorized_count, not_memorized_count, partially_memorized_count],
            ),
        )

    status_stats_table = (
        Table(
            Thead(
                Tr(
                    Th("", cls="uk-table-shrink"),
                    Th("Memorized", cls="min-w-28"),
                    Th("Not Memorized", cls="min-w-28"),
                    Th("Partially Memorized", cls="min-w-28"),
                )
            ),
            Tbody(*map(render_stat_row, ["juz", "surah", "page"])),
        ),
    )

    progress_bar_with_stats = (
        DivCentered(
            P(
                f"Memorization Progress: {format_number(total_memorized_pages)}/604 Pages ({int(total_memorized_pages/604*100)}%)",
                cls="font-bold text-sm sm:text-lg ",
            ),
            Progress(value=f"{total_memorized_pages}", max="604"),
            Div(status_stats_table, cls=FlexT.block),
            cls="space-y-2",
        ),
    )
    modal = ModalContainer(
        ModalDialog(
            ModalHeader(
                ModalTitle(id="my-modal-title"),
                P(cls=TextPresets.muted_sm, id="my-modal-description"),
                ModalCloseButton(),
                cls="space-y-3",
            ),
            Form(
                ModalBody(
                    Div(id="my-modal-body"),
                    data_uk_overflow_auto=True,
                ),
                ModalFooter(Button("Set to Memorized", cls="bg-green-600 text-white")),
                hx_post=f"/partial_memorization_status/{current_type}"
                + (f"?status={status}" if status else ""),
                hx_target="#my-modal",
            ),
            cls="uk-margin-auto-vertical",
        ),
        id="my-modal",
    )
    return main_area(
        Div(
            progress_bar_with_stats,
            DividerLine(),
            filter_btns,
            Form(
                TabContainer(
                    *map(render_navigation_item, ["juz", "surah", "page"]),
                ),
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("Name"),
                                Th("Range / Details"),
                                Th("Status"),
                                Th(""),
                            )
                        ),
                        Tbody(*rows),
                    ),
                    cls="h-[45vh] overflow-auto uk-overflow-auto",
                ),
                cls="space-y-5",
            ),
            Div(modal),
            cls="space-y-5",
        ),
        auth=auth,
        active="Memorization Status",
    )


# This is responsible for updating the modal
@app.get("/partial_memorization_status/{current_type}/{type_number}")
def filtered_table_for_modal(
    current_type: str, type_number: int, title: str, description: str, auth
):
    if current_type == "juz":
        condition = f"pages.juz_number = {type_number}"
    elif current_type == "surah":
        condition = f"items.surah_id = {type_number}"
    elif current_type == "page":
        condition = f"pages.page_number = {type_number}"
    else:
        return "Invalid current_type"

    qry = f"""SELECT items.id, items.surah_id, pages.page_number, pages.juz_number, hafizs_items.status FROM items 
                          LEFT JOIN pages ON items.page_id = pages.id
                          LEFT JOIN hafizs_items ON items.id = hafizs_items.item_id AND hafizs_items.hafiz_id = {auth}
                          WHERE items.active != 0 AND {condition}"""
    ct = db.q(qry)

    def render_row(record):
        return Tr(
            Td(
                # This hidden input is to send the id to the backend even if it is unchecked
                Hidden(name=f"id-{record['id']}", value="0"),
                CheckboxX(
                    name=f"id-{record['id']}",
                    value="1",
                    cls="partial_rows",  # Alpine js reference
                    checked=record["status"] == "memorized",
                    _at_click="handleCheckboxClick($event)",
                ),
            ),
            Td(record["page_number"]),
            Td(surahs[record["surah_id"]].name),
            Td(f"Juz {record['juz_number']}"),
            Td(
                destandardize_text(
                    record["status"] if record["status"] else "not_memorized"
                )
            ),
        )

    table = Table(
        Thead(
            Tr(
                Th(
                    CheckboxX(
                        cls="select_all",
                        x_model="selectAll",
                        _at_change="toggleAll()",
                    )
                ),
                Th("Page"),
                Th("Surah"),
                Th("Juz"),
                Th("Status"),
            )
        ),
        Tbody(*map(render_row, ct)),
        x_data=select_all_checkbox_x_data(
            class_name="partial_rows", is_select_all="false"
        ),
        x_init="updateSelectAll()",
    )

    return (
        table,
        ModalTitle(
            f"{title} - Select Memorized Pages",
            id="my-modal-title",
            hx_swap_oob="true",
        ),
        P(
            description,
            id="my-modal-description",
            hx_swap_oob="true",
            cls=TextPresets.muted_lg,
        ),
    )


@app.post("/partial_memorization_status/{current_type}")
async def update_page_status(current_type: str, req: Request, status: str = None):
    form_data = await req.form()

    for id_str, check in form_data.items():
        if not id_str.startswith("id-"):
            break
        # extract id from the key
        id = int(id_str.split("-")[1])
        # based check value update status
        updated_status = "memorized" if int(check) == 1 else None
        current_hafiz_items = hafizs_items(where=f"item_id = {id}")
        if current_hafiz_items:
            current_hafiz_items = current_hafiz_items[0]
            if not int(check) and current_hafiz_items.status != "memorized":
                pass
            else:
                current_hafiz_items.status = updated_status
            hafizs_items.update(current_hafiz_items)
        else:
            page_number = items[id].page_id
            hafizs_items.insert(
                item_id=id, status=updated_status, mode_id=1, page_number=page_number
            )

    return Redirect(
        f"/memorization_status/{current_type}" + (f"?status={status}" if status else "")
    )


@app.get
def backup():
    if not os.path.exists(DB_PATH):
        return Titled("Error", P("Database file not found"))

    backup_path = backup_sqlite_db(DB_PATH, "data/backup")

    return FileResponse(backup_path, filename="quran_backup.db")


@app.get
def import_db(auth):
    current_dbs = [
        Li(f, cls=ListT.circle) for f in os.listdir("data") if f.endswith(".db")
    ]
    form = Form(
        UploadZone(
            DivCentered(Span("Upload Zone"), UkIcon("upload")),
            id="file",
            accept=".db",
        ),
        Button("Submit"),
        action=import_db,
        method="POST",
    )
    return main_area(
        Div(
            Div(H2("Current DBs"), Ul(*current_dbs)),
            Div(H1("Upload DB"), form),
            cls="space-y-6",
        ),
        active="Revision",
        auth=auth,
    )


@app.post
async def import_db(file: UploadFile):
    path = "data/" + file.filename
    if DB_PATH == path:
        return Titled("Error", P("Cannot overwrite the current DB"))

    file_content = await file.read()
    with open(path, "wb") as f:
        f.write(file_content)

    return RedirectResponse(index)


@app.get
def theme():
    return ThemePicker()


def filter_query_records(auth, custom_where=None):
    default = "hafizs_items.status IS NULL AND items.active != 0"
    if custom_where:
        default = f"{custom_where}"
    not_memorized_tb = f"""
        SELECT items.id, items.surah_id, items.surah_name,
        hafizs_items.item_id, hafizs_items.status, hafizs_items.hafiz_id, pages.juz_number, pages.page_number, revisions.revision_date, revisions.id AS revision_id
        FROM items 
        LEFT JOIN hafizs_items ON items.id = hafizs_items.item_id AND hafizs_items.hafiz_id = {auth}
        LEFT JOIN pages ON items.page_id = pages.id
        LEFT JOIN revisions ON items.id = revisions.item_id
        WHERE {default};
    """
    return db.q(not_memorized_tb)


def group_by_type(data, current_type):
    columns_map = {
        "juz": "juz_number",
        "surah": "surah_id",
        "page": "page_number",
        "item_id": "item_id",
        "id": "id",
    }
    grouped = defaultdict(
        list
    )  # defaultdict() is creating the key as the each column_map number and value as the list of records
    for row in data:
        grouped[row[columns_map[current_type]]].append(row)
    return grouped


def get_closest_unmemorized_item_id(auth, last_newly_memorized_item_id: int):
    not_memorized = filter_query_records(auth)
    not_memorized_item_ids = list(group_by_type(not_memorized, "id").keys())

    def get_continue_page(not_memorized_item_ids, last_newly_memorized_item_id):
        sorted_item_ids = sorted(not_memorized_item_ids)
        for item_id in sorted_item_ids:
            if item_id > last_newly_memorized_item_id:
                return item_id
        return None

    continue_page = get_continue_page(
        not_memorized_item_ids, last_newly_memorized_item_id
    )
    return continue_page


def render_row_based_on_type(
    type_number: str,
    records: list,
    current_type,
    row_link: bool = True,
    continue_new_memorization=False,
    auth=None,
    title_range=None,
    details_range=None,
):
    _surahs = sorted({r["surah_id"] for r in records})
    _pages = sorted([r["page_number"] for r in records])
    _juzs = sorted({r["juz_number"] for r in records})

    def render_range(list, _type=""):
        first_description = list[0]
        last_description = list[-1]

        if _type == "Surah":
            _type = ""
            first_description = surahs[first_description].name
            last_description = surahs[last_description].name

        if len(list) == 1:
            return f"{_type} {first_description}"
        return f"{_type}{"" if _type == "" else "s"} {first_description} – {last_description}"

    surah_range = render_range(_surahs, "Surah")
    page_range = render_range(_pages, "Page")
    juz_range = render_range(_juzs, "Juz")

    if current_type == "juz":
        details = f"{surah_range} ({page_range})"
    elif current_type == "surah":
        details = f"{juz_range} ({page_range})"
    elif current_type == "page":
        details = f"{juz_range} | {surah_range}"
    title = (
        f"{current_type.capitalize()} {type_number}"
        if current_type != "surah"
        else surahs[type_number].name
    )

    filter_url = f"/new_memorization/filter/{current_type}/{type_number}"
    if current_type == "page":
        item_ids = [item.id for item in items(where=f"page_id = {type_number}")]
        get_page = (
            f"/new_memorization/add/{current_type}?item_id={item_ids[0]}"
            if len(item_ids) == 1
            else filter_url
        )
        if continue_new_memorization:
            next_page_item_id = get_closest_unmemorized_item_id(auth, item_ids[0])
            get_page = (
                f"/new_memorization/add/{current_type}?item_id={next_page_item_id}"
            )
            title = title_range
            details = details_range
    else:
        get_page = filter_url

    hx_attrs = {
        "hx_get": get_page,
        "hx_vals": '{"title": "CURRENT_TITLE", "description": "CURRENT_DETAILS"}'.replace(
            "CURRENT_TITLE", title
        ).replace(
            "CURRENT_DETAILS", details
        ),
        "target_id": "modal-body",
        "data_uk_toggle": "target: #modal",
    }

    return Tr(
        Td(title),
        Td(details),
        (
            Td(
                A(
                    (
                        f"Show Pages ➡️"
                        if current_type != "page"
                        else (
                            "Continue ➡️"
                            if continue_new_memorization
                            else "Start Memorization ➡️"
                        )
                    ),
                    **hx_attrs if continue_new_memorization else {},
                    cls=AT.classic,
                ),
                cls="text-right",
            )
        ),
        **hx_attrs if row_link else {},
    )


def render_navigation_item(
    _type: str,
    current_type: str,
):
    return Li(
        A(
            f"by {_type}",
            href=f"/new_memorization/{_type}",
        ),
        cls=("uk-active" if _type == current_type else None),
    )


def flatten_input(data):
    if not data:
        return []
    seen = set()  # use a set to filtered out duplicate entries
    flat = []  # use a list to get order
    for page, records in data:
        for entry in records:
            key = entry["page_number"]
            if key not in seen:
                flat.append(entry)
                seen.add(key)
    return flat


def group_consecutive_by_date(records):
    if not records:
        return []
    # Sort by page_number ASC so we can group sequence pages
    records = sorted(records, key=lambda x: x["page_number"])

    groups = []
    current_group = [records[0]]

    for prev, curr in zip(records, records[1:]):
        # Consecutive pages and same date
        is_consecutive = curr["page_number"] == prev["page_number"] + 1
        same_date = curr["revision_date"] == prev["revision_date"]

        if is_consecutive and same_date:
            current_group.append(curr)
        else:
            groups.append(current_group)
            current_group = [curr]

    groups.append(current_group)

    # Sort final groups by latest revision_id in descending order
    def latest_revision(group):
        return max(item["revision_date"] for item in group)

    sorted_groups = sorted(groups, key=latest_revision, reverse=True)
    return sorted_groups


def format_output(groups: list):
    formatted = {}
    for group in groups:
        pages = [item["page_number"] for item in group]
        juz = group[0]["juz_number"]
        surahs = list(
            dict.fromkeys(item["surah_name"] for item in group)
        )  # get list of unique surahs
        page_str = (
            f"Page {pages[0]}" if len(pages) == 1 else f"Pages {pages[0]} - {pages[-1]}"
        )
        surah_str = " - ".join(surahs)
        title = page_str
        details = f"Juz {juz} | {surah_str}"

        for page in pages:
            formatted[page] = (title, details)
    return formatted


@app.get("/new_memorization/{current_type}")
def new_memorization(auth, current_type: str):
    if not current_type:
        current_type = "juz"
    ct = filter_query_records(auth)
    grouped = group_by_type(ct, current_type)
    not_memorized_rows = [
        render_row_based_on_type(type_number, records, current_type)
        for type_number, records in list(grouped.items())
    ]
    not_memorized_table = Div(
        Table(
            Thead(
                Tr(
                    Th("NAME"),
                    Th("RANGE/DETAILS"),
                ),
            ),
            Tbody(*not_memorized_rows),
        ),
        cls="uk-overflow-auto h-[45vh] p-4",
    )
    modal = ModalContainer(
        ModalDialog(
            ModalHeader(
                ModalTitle(id="modal-title"),
                P(cls=TextPresets.muted_sm, id="modal-description"),
                ModalCloseButton(),
                cls="space-y-3",
            ),
            ModalBody(
                Div(id="modal-body"),
                data_uk_overflow_auto=True,
            ),
            ModalFooter(),
            cls="uk-margin-auto-vertical",
        ),
        id="modal",
    )

    where_query = """revisions.mode_id = 2 AND hafizs_items.status IS 'newly memorized' AND items.active != 0 ORDER BY revisions.revision_date DESC, revisions.id DESC"""
    newly_memorized = filter_query_records(auth, where_query)
    grouped = group_by_type(newly_memorized, "page")
    grouped_list = list(grouped.items())

    if grouped_list:
        flat = flatten_input(grouped_list)
        consecutive_groups = group_consecutive_by_date(flat)

        def group_latest_sort_key(group):
            latest = max(group, key=lambda x: (x["revision_date"], x["revision_id"]))
            return (latest["revision_date"], latest["revision_id"])

        consecutive_groups_sorted = sorted(
            consecutive_groups, key=group_latest_sort_key, reverse=True
        )
    else:
        consecutive_groups_sorted = []

    def render_memorized_row(group, auth):
        if not group:
            return None
        formatted = format_output([group])
        first_page = group[0]["page_number"]
        title_range, details_range = formatted[first_page]
        return render_row_based_on_type(
            first_page,
            group,
            "page",
            row_link=False,
            continue_new_memorization=True,
            auth=auth,
            title_range=title_range,
            details_range=details_range,
        )

    newly_memorized_rows = list(
        filter(
            None,
            [render_memorized_row(group, auth) for group in consecutive_groups_sorted],
        )
    )

    recent_newly_memorized_table = Div(
        Table(
            Thead(
                Tr(
                    Th("NAME"),
                    Th("RANGE/DETAILS"),
                ),
            ),
            Tbody(*newly_memorized_rows),
        ),
        cls="uk-overflow-auto h-[25vh] p-4",
    )

    return main_area(
        H1("New Memorization", cls="uk-text-center"),
        Div(
            Div(
                H4("Recently Memorized Pages"), recent_newly_memorized_table, cls="mt-4"
            ),
            Div(
                H4("Select a Page Not Yet Memorized"),
                TabContainer(
                    *map(
                        lambda nav: render_navigation_item(nav, current_type),
                        ["juz", "surah", "page"],
                    ),
                ),
                not_memorized_table,
            ),
            cls="space-y-4",
        ),
        Div(modal),
        active="New Memorization",
        auth=auth,
    )


@app.get("/new_memorization/filter/{current_type}/{type_number}")
def filtered_table_for_new_memorization_modal(
    auth, current_type: str, type_number: int, title: str, description: str
):
    if current_type == "juz":
        condition = f"pages.juz_number = {type_number}"
    elif current_type == "surah":
        condition = f"items.surah_id = {type_number}"
    elif current_type == "page":
        condition = f"pages.page_number = {type_number}"
    else:
        return "Invalid current_type"

    qry = f"""SELECT items.id, items.surah_id, pages.page_number, pages.juz_number, hafizs_items.status FROM items
                          LEFT JOIN pages ON items.page_id = pages.id
                          LEFT JOIN hafizs_items ON items.id = hafizs_items.item_id AND hafizs_items.hafiz_id = {auth}
                          WHERE items.active != 0 AND hafizs_items.status IS NULL AND {condition}"""
    ct = db.q(qry)

    def render_row(record):
        return Tr(
            Td(
                # This hidden input is to send the id to the backend even if it is unchecked
                CheckboxX(
                    name=f"item_ids",
                    value=record["id"],
                    cls="partial_rows",  # Alpine js reference
                    _at_click="handleCheckboxClick($event)",
                ),
            ),
            Td(record["page_number"]),
            Td(surahs[record["surah_id"]].name),
            Td(f"Juz {record['juz_number']}"),
            Td(
                A(
                    f"Start Memorization ➡️",
                    hx_get=f"/new_memorization/add/{current_type}?item_id={record['id']}",
                    hx_vals='{"title": "CURRENT_TITLE", "description": "CURRENT_DETAILS"}'.replace(
                        "CURRENT_TITLE", title
                    ).replace(
                        "CURRENT_DETAILS", description
                    ),
                    hx_target="#modal-body",
                    cls=(AT.classic),
                ),
                cls="text-right",
            ),
        )

    table = Div(
        Table(
            Thead(
                Tr(
                    Th(
                        CheckboxX(
                            cls="select_all",
                            x_model="selectAll",
                            _at_change="toggleAll()",
                        )
                    ),
                    Th("Page"),
                    Th("Surah"),
                    Th("Juz"),
                )
            ),
            Tbody(*map(render_row, ct)),
            x_data=select_all_checkbox_x_data(
                class_name="partial_rows", is_select_all="false"
            ),
            x_init="updateSelectAll()",
        ),
        cls="uk-overflow-auto max-h-[75vh] p-4",
    )

    return (
        Form(
            table,
            Button("Bulk Entry", cls="bg-green-600 text-white"),
            hx_get=f"/new_memorization/bulk_add/{current_type}",
            hx_target="#modal-body",
            cls="space-y-2",
        ),
        ModalTitle(
            f"{title} - Select Memorized Page", id="modal-title", hx_swap_oob="true"
        ),
        P(
            description,
            id="modal-description",
            hx_swap_oob="true",
            cls=TextPresets.muted_lg,
        ),
    )


def create_new_memorization_revision_form(
    current_type: str, title: str, description: str
):
    def RadioLabel(o):
        value, label = o
        is_checked = True if value == "1" else False
        return Div(
            FormLabel(
                Radio(
                    id="rating", value=value, checked=is_checked, autofocus=is_checked
                ),
                Span(label),
                cls="space-x-2",
            )
        )

    return Div(
        Form(
            LabelInput(
                "Revision Date",
                name="revision_date",
                type="date",
                value=current_time("%Y-%m-%d"),
            ),
            Input(name="page_no", type="hidden"),
            Input(name="mode_id", type="hidden"),
            Input(name="item_id", type="hidden"),
            Div(
                FormLabel("Rating"),
                *map(RadioLabel, RATING_MAP.items()),
                cls="space-y-2 leading-8 sm:leading-6 ",
            ),
            Div(
                Button("Save", cls=ButtonT.primary),
                A(
                    Button("Cancel", type="button", cls=ButtonT.secondary),
                    href=f"/new_memorization/{current_type}",
                ),
                cls="flex justify-around items-center w-full",
            ),
            action=f"/new_memorization/add/{current_type}",
            method="POST",
        ),
        ModalTitle(
            f"{title} - Select Memorized Page", id="modal-title", hx_swap_oob="true"
        ),
        P(
            description,
            id="modal-description",
            hx_swap_oob="true",
            cls=TextPresets.muted_lg,
        ),
    )


@rt("/new_memorization/add/{current_type}")
def get(
    current_type: str,
    item_id: str,
    title: str = None,
    description: str = None,
    max_item_id: int = 836,
    date: str = None,
):
    item_id = int(item_id)
    if item_id >= max_item_id:
        return Redirect(new_memorization)

    page = items[item_id].page_id
    return Titled(
        f"{page} - {get_surah_name(item_id=item_id)} - {items[item_id].start_text}",
        fill_form(
            create_new_memorization_revision_form(current_type, title, description),
            {
                "page_no": page,
                "mode_id": 2,
                "plan_id": None,
                "revision_date": date,
                "item_id": item_id,
            },
        ),
    )


@rt("/new_memorization/add/{current_type}")
def post(current_type: str, page_no: int, item_id: int, revision_details: Revision):
    # The id is set to zer in the form, so we need to delete it
    # before inserting to generate the id automatically
    del revision_details.id
    revision_details.plan_id = set_zero_to_none(revision_details.plan_id)
    try:
        hafizs_items(where=f"item_id = {item_id}")[0]
    except IndexError:
        # updating the status of the item to memorized
        hafizs_items.insert(Hafiz_Items(item_id=item_id, page_number=page_no))
    hafizs_items_id = hafizs_items(where=f"item_id = {item_id}")[0].id
    hafizs_items.update(
        {"status": "newly memorized", "mode_id": revision_details.mode_id},
        hafizs_items_id,
    )
    revisions.insert(revision_details)
    return Redirect(f"/new_memorization/{current_type}")


@app.get("/new_memorization/bulk_add/{current_type}")
def get(
    auth,
    item_ids: list[int],
    current_type: str = "juz",
    # is_part is to determine whether it came from single entry page or not
    is_part: bool = False,
    revision_date: str = None,
):

    def _render_row(item_id):

        def _render_radio(o):
            value, label = o
            is_checked = True if value == "1" else False
            return FormLabel(
                Radio(
                    id=f"rating-{item_id}",
                    value=value,
                    checked=is_checked,
                    cls="toggleable-radio",
                ),
                Span(label),
                cls="space-x-2",
            )

        current_page_details = items[item_id]
        return Tr(
            Td(
                CheckboxX(
                    name="ids",
                    value=item_id,
                    cls="revision_ids",
                    _at_click="handleCheckboxClick($event)",
                )
            ),
            Td(current_page_details.surah_name),
            Td(P(current_page_details.page_id)),
            Td(current_page_details.part),
            Td(P(current_page_details.start_text, cls=(TextT.xl))),
            Td(
                Div(
                    *map(_render_radio, RATING_MAP.items()),
                    cls=(FlexT.block, FlexT.row, FlexT.wrap, "gap-x-6 gap-y-4"),
                )
            ),
        )

    table = Table(
        Thead(
            Tr(
                Th(
                    CheckboxX(
                        cls="select_all", x_model="selectAll", _at_change="toggleAll()"
                    )
                ),
                Th("Surah"),
                Th("Page"),
                Th("Part"),
                Th("Start"),
                Th("Rating"),
            )
        ),
        Tbody(*map(_render_row, item_ids)),
        x_data=select_all_checkbox_x_data(
            class_name="revision_ids",
            is_select_all="true" if len(item_ids) != 0 else "false",
        ),
        x_init="toggleAll()",
    )

    action_buttons = Div(
        Button(
            "Save",
            cls=ButtonT.primary,
        ),
        A(
            Button("Cancel", type="button", cls=ButtonT.secondary),
            href=f"/new_memorization/{current_type}",
        ),
        cls=(FlexT.block, FlexT.around, FlexT.middle, "w-full"),
    )
    start_description = f"{get_surah_name(item_id=item_ids[0])}"
    end_description = (
        f" => {items[item_ids[-1]].page_id} - {get_surah_name(item_id=item_ids[-1])}"
    )
    description = f"{items[item_ids[0]].page_id} - {start_description}"
    return Titled(
        (description if len(item_ids) == 1 else description + f"{end_description}"),
        Form(
            Hidden(name="mode_id", value=2),
            Hidden(name="plan_id", value=None),
            LabelInput(
                "Revision Date",
                name="revision_date",
                type="date",
                value=(revision_date or current_time("%Y-%m-%d")),
            ),
            Div(table, cls="uk-overflow-auto"),
            action_buttons,
            action=f"/new_memorization/bulk_add/{current_type}",
            method="POST",
        ),
        Script(src="/public/script.js"),
        active="Revision",
        auth=auth,
    )


@rt("/new_memorization/bulk_add/{current_type}")
async def post(
    revision_date: str,
    mode_id: int,
    plan_id: int,
    current_type: str,
    auth,
    req,
):
    plan_id = None
    form_data = await req.form()
    item_ids = form_data.getlist("ids")
    parsed_data = []
    for name, value in form_data.items():
        if name.startswith("rating-"):
            item_id = name.split("-")[1]
            if item_id in item_ids:
                try:
                    hafizs_items_id = hafizs_items(where=f"item_id = {item_id}")[0]
                except IndexError:
                    hafizs_items.insert(
                        Hafiz_Items(item_id=item_id, page_number=items[item_id].page_id)
                    )
                hafizs_items_id = hafizs_items(where=f"item_id = {item_id}")[0].id
                hafizs_items.update(
                    {"status": "newly memorized", "mode_id": mode_id}, hafizs_items_id
                )
                parsed_data.append(
                    Revision(
                        item_id=int(item_id),
                        rating=int(value),
                        hafiz_id=auth,
                        revision_date=revision_date,
                        mode_id=mode_id,
                        plan_id=plan_id,
                    )
                )

    revisions.insert_all(parsed_data)
    return Redirect(f"/new_memorization/{current_type}")


serve()
