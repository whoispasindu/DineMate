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


def test_seats_are_placed_inside_zones_and_set_capacity() -> None:
    editor = ZoneEditor(1000, 1000)
    square(editor, 100, 100, 400)
    press(editor, [ENTER])
    press(editor, "s")
    press(editor, [ENTER])
    press(editor, "6")
    press(editor, [ENTER])
    press(editor, "t")
    assert editor.mode == "seats"
    editor.click(200, 200)
    editor.click(300, 200)
    editor.click(900, 900)
    assert "inside a seating zone" in editor.prompt()
    editor.click(400, 400)
    press(editor, "u")
    zone = editor.layout()["zones"][0]
    assert zone["capacity"] == 2
    assert zone["seats"] == [{"seat_id": "seat-1", "x": 0.2, "y": 0.2}, {"seat_id": "seat-2", "x": 0.3, "y": 0.2}]
    press(editor, "t")
    assert editor.mode == "points"


def test_seats_survive_loading_a_layout() -> None:
    editor = ZoneEditor(1000, 1000)
    editor.load(
        {
            "zones": [
                {
                    "name": "Front",
                    "capacity": 9,
                    "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
                    "seats": [{"seat_id": "a1", "x": 0.2, "y": 0.2}],
                }
            ]
        }
    )
    press(editor, "t")
    editor.click(300, 300)
    zone = editor.layout()["zones"][0]
    assert [s["seat_id"] for s in zone["seats"]] == ["a1", "seat-2"]
    assert zone["capacity"] == 2


def test_work_areas_get_their_own_keys_and_need_no_name() -> None:
    editor = ZoneEditor(1000, 1000)
    for key, area in (("k", "counter"), ("h", "kitchen"), ("f", "floor")):
        square(editor)
        press(editor, [ENTER])
        assert "K counter" in editor.prompt()
        press(editor, key)
        assert editor.mode == "points"
        assert f"Added {area} work area" in editor.prompt()
    layout = editor.layout()
    assert [w["area"] for w in layout["work"]] == ["counter", "kitchen", "floor"]
    assert layout["work"][0]["points"][0] == [0.1, 0.1]
    assert layout["zones"] == [] and layout["ignore"] == []


def test_a_layout_with_only_work_areas_can_be_saved() -> None:
    editor = ZoneEditor(800, 600)
    square(editor)
    press(editor, [ENTER])
    press(editor, "k")
    assert press(editor, "s") == ["save"]


def test_work_areas_survive_loading_and_stay_out_of_ignore() -> None:
    editor = ZoneEditor(800, 600)
    editor.load(
        {
            "zones": [],
            "ignore": [
                {"type": "queue", "points": [[0, 0.5], [0.5, 0.5], [0.5, 1]]},
                {"type": "work", "area": "kitchen", "points": [[0.5, 0], [1, 0], [1, 0.5]]},
            ],
            "work": [{"area": "counter", "points": [[0, 0], [0.5, 0], [0.5, 0.5]]}],
        }
    )
    assert "2 work area(s)" in editor.prompt()
    layout = editor.layout()
    assert [w["area"] for w in layout["work"]] == ["counter", "kitchen"]
    assert [a["type"] for a in layout["ignore"]] == ["queue"]
    press(editor, "d")
    assert [a["type"] for a in editor.layout()["ignore"]] == []
