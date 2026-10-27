from vision.zone_editor import ZoneEditor

ENTER, ESC, BACKSPACE, NO_KEY = 13, 27, 8, 255


def press(editor: ZoneEditor, keys: str | list[int]) -> list[object]:
    codes = [ord(c) for c in keys] if isinstance(keys, str) else keys
    return [editor.key(c) for c in codes]


def square(editor: ZoneEditor, x0: int = 100, y0: int = 100, size: int = 200) -> None:
    for x, y in [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]:
        editor.click(x, y)


def test_full_seating_zone_flow_stays_in_window() -> None:
    editor = ZoneEditor(1000, 500)
    square(editor)
    press(editor, [ENTER])
    assert editor.mode == "type"
    press(editor, "s")
    assert editor.mode == "name"
    press(editor, "Front tablesx")
    press(editor, [BACKSPACE, ENTER])
    assert editor.mode == "capacity"
    press(editor, "12")
    press(editor, [ENTER])
    assert editor.mode == "points"
    zone = editor.layout()["zones"][0]
    assert (zone["name"], zone["capacity"]) == ("Front tables", 12)
    assert zone["points"][0] == [0.1, 0.2]
    assert "Added seating zone" in editor.prompt()


def test_typing_s_in_the_name_does_not_save() -> None:
    editor = ZoneEditor(800, 600)
    square(editor)
    press(editor, [ENTER])
    press(editor, "s")
    assert press(editor, "Seats") == [None] * 5
    assert editor.text == "Seats"


def test_walkway_needs_no_name() -> None:
    editor = ZoneEditor(800, 600)
    square(editor)
    press(editor, [ENTER])
    press(editor, "w")
    assert editor.layout()["ignore"][0]["type"] == "walkway"
    assert editor.mode == "points"


def test_save_requires_a_seating_zone_and_quit_works() -> None:
    editor = ZoneEditor(800, 600)
    assert press(editor, "s") == [None]
    assert "at least one seating zone" in editor.prompt()
    assert press(editor, "q") == ["quit"]


def test_shape_needs_three_points_and_clicks_ignored_while_typing() -> None:
    editor = ZoneEditor(800, 600)
    editor.click(10, 10)
    editor.click(20, 20)
    press(editor, [ENTER])
    assert editor.mode == "points" and "3 points" in editor.prompt()
    editor.click(30, 10)
    press(editor, [ENTER])
    editor.click(400, 400)
    assert len(editor.current) == 3


def test_blank_name_and_capacity_get_defaults_and_escape_cancels() -> None:
    editor = ZoneEditor(800, 600)
    square(editor)
    press(editor, [ENTER])
    press(editor, "s")
    press(editor, [ENTER, ENTER])
    zone = editor.layout()["zones"][0]
    assert (zone["name"], zone["capacity"]) == ("Zone 1", 4)
    square(editor)
    press(editor, [ENTER, ESC])
    assert editor.mode == "points" and editor.current == []
    square(editor)
    press(editor, [ESC])
    assert editor.current == []
    assert press(editor, [NO_KEY, -1]) == [None, None]


def test_saved_layout_loads_for_editing_and_d_deletes_last_area() -> None:
    editor = ZoneEditor(800, 600)
    editor.load(
        {
            "zones": [{"name": "Tables", "capacity": 20, "points": [[0.1, 0.5], [0.9, 0.5], [0.9, 0.9]]}],
            "ignore": [{"type": "walkway", "points": [[0, 0], [1, 0], [1, 0.2]]}],
        }
    )
    assert "Loaded 1 seating zone" in editor.prompt()
    assert editor.layout()["zones"][0]["name"] == "Tables"
    press(editor, "d")
    assert editor.layout()["ignore"] == []
    assert press(editor, "s") == ["save"]


def test_d_does_nothing_while_drawing_a_shape() -> None:
    editor = ZoneEditor(800, 600)
    square(editor)
    press(editor, [ENTER])
    press(editor, "w")
    editor.click(10, 10)
    press(editor, "d")
    assert len(editor.shapes) == 1 and len(editor.current) == 1
