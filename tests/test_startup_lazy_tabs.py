from types import SimpleNamespace

import baza_skryptow as bs
from baza_skryptow import CodeMate


class _Frame:
    def __init__(self):
        self.packed = 0

    def pack_forget(self):
        pass

    def pack(self, **kwargs):
        self.packed += 1


class _Button:
    def configure(self, **kwargs):
        pass


def test_main_tab_is_built_once_when_first_selected():
    builds = []
    frame = _Frame()
    app = SimpleNamespace(
        _main_tab_keys=["tab_szukaj"],
        _main_tab_builders={},
        _main_tabs_built=set(),
        _main_btns=[_Button()],
        main_frames={},
        _update_minsize=lambda *a, **k: None,
    )

    def build_search_tab():
        builds.append("szukaj")
        app.main_frames["szukaj"] = frame

    app._main_tab_builders["tab_szukaj"] = build_search_tab

    def show():
        app.main_frames["szukaj"].pack(fill="both", expand=True)

    CodeMate._sel_main(app, 0, show)
    CodeMate._sel_main(app, 0, show)

    assert builds == ["szukaj"]
    assert frame.packed == 2


def test_general_context_menu_is_opened_once_by_event_handler():
    popup_calls = []

    class _Menu:
        def add_command(self, **_kwargs):
            pass

        def add_separator(self):
            pass

        def add_cascade(self, **_kwargs):
            pass

        def tk_popup(self, x, y):
            popup_calls.append((x, y))

    menu = _Menu()
    app = SimpleNamespace(
        _menu_nowy_skrypt=lambda: None,
        _menu_pokaz_liste=lambda: None,
        _menu_pokaz_szukaj=lambda: None,
        _zapisz=lambda: None,
        _menu_odswiez=lambda: None,
        _menu_o_programie=lambda: None,
    )
    mouse = SimpleNamespace(
        _ctx_menu=None,
        app=app,
        _make_menu=lambda: menu,
        _add_zoom_submenu=lambda _menu: None,
    )
    mouse._build_general_menu = lambda target_menu, target_app: (
        bs.MouseManager._build_general_menu(mouse, target_menu, target_app))

    bs.MouseManager._build_general_menu(mouse, menu, app)
    assert popup_calls == []

    event = SimpleNamespace(widget=object(), x_root=120, y_root=240)
    bs.MouseManager._show_context_menu(mouse, event)

    assert popup_calls == [(120, 240)]


def test_subtab_is_built_once_when_first_selected():
    builds = []
    attachments = []
    frame = _Frame()
    app = SimpleNamespace(
        _sub_tab_keys=["edytor"],
        _sub_tab_builders={},
        _sub_tabs_built=set(),
        _sub_btns=[_Button()],
        sub_frames={},
        _attach_editor_highlighter=lambda: attachments.append("edytor"),
        _update_minsize=lambda *a, **k: None,
    )

    def build_editor_tab():
        builds.append("edytor")
        app.sub_frames["edytor"] = frame

    app._sub_tab_builders["edytor"] = build_editor_tab

    def show():
        app.sub_frames["edytor"].pack(fill="both", expand=True)

    CodeMate._sel_sub(app, 0, show)
    CodeMate._sel_sub(app, 0, show)

    assert builds == ["edytor"]
    assert attachments == ["edytor"]
    assert frame.packed == 2


def test_shared_runner_frame_is_built_once_for_both_entry_points():
    app = SimpleNamespace(_runner_frame_built=False)
    builds = []

    def build_runner_frame():
        builds.append("runner")

    app._build_sub_runner = build_runner_frame

    CodeMate._ensure_runner_frame(app)
    CodeMate._ensure_runner_frame(app)

    assert builds == ["runner"]


def test_git_integration_is_created_once_when_first_requested(monkeypatch):
    created = []

    class _Git:
        def __init__(self, path, auto_commit):
            created.append((path, auto_commit))

        def is_available(self):
            return True

    monkeypatch.setattr(bs, "GitIntegration", _Git)
    app = SimpleNamespace(_git_enabled=True, _git=None)

    first = CodeMate._ensure_git(app)
    second = CodeMate._ensure_git(app)

    assert first is second
    assert len(created) == 1


def test_git_stage_and_unstage_operate_only_on_selected_files():
    operations = []

    class _ChangesTree:
        def selection(self):
            return ("file-2",)

    class _Git:
        def add_file(self, path):
            operations.append(("stage", path))
            return True

        def unstage_file(self, path):
            operations.append(("unstage", path))
            return True

    app = SimpleNamespace(
        _git_changed_paths={"file-1": "one.py", "file-2": "two.py"},
        _git_changes_tree=_ChangesTree(),
        _git=_Git(),
        _git_selected_change_paths=lambda: [
            app._git_changed_paths[iid] for iid in app._git_changes_tree.selection()
            if iid in app._git_changed_paths],
        _git_refresh=lambda: operations.append(("refresh",)),
    )

    CodeMate._git_stage_selected(app)
    CodeMate._git_unstage_selected(app)

    assert operations == [
        ("stage", bs.APP_DIR / "two.py"), ("refresh",),
        ("unstage", bs.APP_DIR / "two.py"), ("refresh",),
    ]


def test_git_discard_requires_confirmation_and_preserves_index(monkeypatch):
    actions = []
    app = SimpleNamespace(
        _git_selected_change_paths=lambda: ["tracked.py"],
        _git=SimpleNamespace(
            status=lambda: {"modified": ["tracked.py"], "untracked": []},
            restore_worktree_file=lambda path: actions.append(("restore", path)) or True),
        _git_refresh=lambda: actions.append(("refresh",)),
    )
    prompts = []
    monkeypatch.setattr(
        bs.messagebox, "askyesno",
        lambda title, message: prompts.append((title, message)) or True)

    bs._set_lang("pl")
    CodeMate._git_discard_worktree_selected(app)

    assert prompts[0][0] == "Odrzuć zmiany robocze"
    assert "zmiany staged pozostaną" in prompts[0][1]
    assert actions == [
        ("restore", bs.APP_DIR / "tracked.py"), ("refresh",)]


def test_git_discard_skips_untracked_files(monkeypatch):
    actions = []
    app = SimpleNamespace(
        _git_selected_change_paths=lambda: ["new.py"],
        _git=SimpleNamespace(
            status=lambda: {"modified": [], "untracked": ["new.py"]},
            restore_worktree_file=lambda path: actions.append(path) or True),
    )
    prompts = []
    monkeypatch.setattr(
        bs.messagebox, "showinfo",
        lambda title, message: prompts.append((title, message)))
    monkeypatch.setattr(
        bs.messagebox, "askyesno",
        lambda *_args: pytest.fail("untracked files must not be discarded"))

    CodeMate._git_discard_worktree_selected(app)

    assert actions == []
    assert prompts


def test_mousewheel_handler_stops_default_tk_scrolling():
    calls = []
    mouse = object.__new__(bs.MouseManager)
    mouse._scroll_axis = lambda widget, axis, units: calls.append((widget, axis, units)) or True
    widget = object()
    event = SimpleNamespace(state=0, widget=widget, num=0, delta=120)

    result = mouse._on_mousewheel_global(event)

    assert result == "break"
    # delta=120 -> 3 jednostki; scroll pionowy dostaje odwrócony znak
    assert calls == [(widget, "y", -3)]


def test_mousewheel_shift_falls_back_to_vertical_when_no_horizontal_scroll():
    calls = []
    mouse = object.__new__(bs.MouseManager)

    def fake_scroll(widget, axis, units):
        calls.append((widget, axis, units))
        return axis == "y"  # poziomo nic nie da się przewinąć

    mouse._scroll_axis = fake_scroll
    widget = object()
    event = SimpleNamespace(state=0x1, widget=widget, num=0, delta=120)

    result = mouse._on_mousewheel_global(event)

    assert result == "break"
    assert calls == [(widget, "x", 3), (widget, "y", -3)]


def test_scroll_axis_walks_widget_chain_and_stops_at_first_moved():
    """_scroll_axis przewija najbliższy przewijany widget; przy krawędzi
    propaguje do przodka."""
    import tkinter as tk

    root = tk.Tk()
    try:
        mouse = object.__new__(bs.MouseManager)
        canvas = tk.Canvas(root, width=200, height=80)
        canvas.pack()
        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        for i in range(60):
            tk.Label(inner, text=f"wiersz {i}").pack()
        canvas.configure(scrollregion=(0, 0, 200, 1200))
        leaf = inner.winfo_children()[5]
        root.update()

        assert mouse._scroll_axis(leaf, "y", 3) is True
        assert canvas.yview()[0] > 0
    finally:
        root.destroy()


def test_shift_linux_wheel_uses_global_handler_and_stops_vertical_scroll():
    bindings = {}
    app = SimpleNamespace(
        bind_all=lambda sequence, callback: bindings.__setitem__(sequence, callback))
    mouse = bs.MouseManager(app)
    calls = []
    mouse._scroll_axis = lambda widget, axis, units: calls.append((widget, axis, units)) or True
    widget = object()
    for sequence, number, expected_units in (
            ("<Shift-Button-4>", 4, 3),
            ("<Shift-Button-5>", 5, -3)):
        event = SimpleNamespace(state=0x1, num=number, delta=0, widget=widget)
        result = bindings[sequence](event)

        assert bindings[sequence] == mouse._on_mousewheel_global
        assert result == "break"
        assert calls[-1] == (widget, "x", expected_units)

    assert len(calls) == 2


def test_runner_double_click_runs_only_clicked_row():
    calls = []

    class _Listbox:
        def nearest(self, y):
            return 2

        def bbox(self, row):
            return (0, 20, 100, 10)

        def selection_clear(self, first, last):
            calls.append(("clear", first, last))

        def selection_set(self, row):
            calls.append(("select", row))

    app = SimpleNamespace(
        _runner_list=_Listbox(),
        _runner_pick=lambda: calls.append(("pick",)),
        _runner_start=lambda: calls.append(("run",)),
    )

    result = CodeMate._runner_double_click(app, SimpleNamespace(y=25))

    assert result == "break"
    assert calls == [("clear", 0, "end"), ("select", 2), ("pick",), ("run",)]


def test_runner_double_click_on_blank_space_does_not_run():
    calls = []

    class _Listbox:
        def nearest(self, y):
            return 2

        def bbox(self, row):
            return (0, 20, 100, 10)

    app = SimpleNamespace(_runner_list=_Listbox(), _runner_start=lambda: calls.append("run"))

    result = CodeMate._runner_double_click(app, SimpleNamespace(y=40))

    assert result == "break"
    assert calls == []