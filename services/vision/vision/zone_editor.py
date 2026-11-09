from dataclasses import dataclass, field
from typing import Any, Literal

from vision.geometry import contains

ENTER_KEYS = {10, 13}
BACKSPACE_KEYS = {8, 127}
ESCAPE = 27
AREA_KEYS = {"s": "seating", "q": "queue", "w": "walkway", "i": "ignore"}
WORK_KEYS = {"k": "counter", "h": "kitchen", "f": "floor"}
DEFAULT_CAPACITY = 4
MAX_NAME = 40

Mode = Literal["points", "type", "name", "capacity", "seats"]
Action = Literal["save", "quit"] | None


@dataclass
class ZoneEditor:
    width: int
    height: int
    mode: Mode = "points"
    current: list[tuple[float, float]] = field(default_factory=list)
    shapes: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""
    message: str = ""
    pending: dict[str, Any] = field(default_factory=dict)
    placed: list[dict[str, Any]] = field(default_factory=list)

    def click(self, x: int, y: int) -> None:
        nx = round(min(max(x / self.width, 0.0), 1.0), 4)
        ny = round(min(max(y / self.height, 0.0), 1.0), 4)
        if self.mode == "seats":
            self._add_seat(nx, ny)
        elif self.mode == "points":
            self.current.append((nx, ny))
            self.message = ""

    def _add_seat(self, x: float, y: float) -> None:
        zone = next((s for s in self.shapes if s["type"] == "seating" and contains(s["points"], x, y)), None)
        if zone is None:
            self.message = "Click on a chair inside a seating zone."
            return
        zone.setdefault("seats", []).append({"seat_id": self._new_seat_id(), "x": x, "y": y})
        self.placed.append(zone)
        self.message = f"{zone['name']}: {len(zone['seats'])} seat(s). Click the next chair."

    def _new_seat_id(self) -> str:
        used = {seat["seat_id"] for s in self.shapes for seat in s.get("seats", [])}
        number = len(used) + 1
        while f"seat-{number}" in used:
            number += 1
        return f"seat-{number}"

    def prompt(self) -> str:
        if self.mode == "type":
            return "Type: S seating, Q queue, W walkway, I ignore | Work: K counter, H kitchen, F floor | Esc cancels"
        if self.mode == "name":
            return f"Zone name: {self.text}_   (Enter to continue)"
        if self.mode == "capacity":
            return f"Seats in this zone: {self.text}_   (Enter, blank = {DEFAULT_CAPACITY})"
        if self.mode == "seats":
            prefix = f"{self.message} | " if self.message else ""
            return prefix + "Seats: click each chair where a seated person's hips go | U undo, T done, S save"
        if self.message:
            return self.message
        return "Click corners, Enter closes an area | U undo, D delete area, T place seats | S save, Q quit"

    def key(self, code: int) -> Action:
        if code < 0 or code == 255:
            return None
        char = chr(code).lower() if 32 <= code < 127 else ""
        if self.mode == "points":
            return self._points_key(code, char)
        if self.mode == "seats":
            return self._seats_key(code, char)
        if code == ESCAPE:
            self._reset_pending("Cancelled.")
            return None
        if self.mode == "type":
            self._type_key(char)
        elif self.mode == "name":
            self._name_key(code)
        else:
            self._capacity_key(code, char)
        return None

    def _points_key(self, code: int, char: str) -> Action:
        if code in ENTER_KEYS or char == " ":
            if len(self.current) < 3:
                self.message = "A shape needs at least 3 points."
            else:
                self.mode = "type"
        elif char == "u" and self.current:
            self.current.pop()
        elif char == "t" and not self.current:
            if not any(s["type"] == "seating" for s in self.shapes):
                self.message = "Add a seating zone before placing seats."
            else:
                self.mode, self.message = "seats", ""
        elif char == "d" and not self.current and self.shapes:
            removed = self.shapes.pop()
            self.message = f"Deleted {removed.get('name', removed['type'])}."
        elif char == "s":
            if not any(s["type"] in ("seating", "work") for s in self.shapes):
                self.message = "Add at least one seating zone or work area before saving."
                return None
            return "save"
        elif code == ESCAPE:
            self.current = []
            self.message = "Cleared the shape in progress."
        elif char == "q":
            return "quit"
        return None

    def _seats_key(self, code: int, char: str) -> Action:
        if char == "u":
            while self.placed and (self.placed[-1] not in self.shapes or not self.placed[-1].get("seats")):
                self.placed.pop()
            if self.placed:
                zone = self.placed.pop()
                zone["seats"].pop()
                self.message = f"Removed a seat from {zone['name']}."
            else:
                self.message = "No seats placed yet in this session."
        elif char in ("t", " ") or code in ENTER_KEYS or code == ESCAPE:
            self.mode = "points"
            seats = sum(len(s.get("seats", [])) for s in self.shapes)
            self.message = f"{seats} seat(s) placed. Draw more areas, T for seats, or S to save."
        elif char == "s":
            return "save"
        elif char == "q":
            return "quit"
        return None

    def _type_key(self, char: str) -> None:
        if char in WORK_KEYS:
            self.pending = {"type": "work", "area": WORK_KEYS[char], "points": list(self.current)}
            self._finish()
            return
        area = AREA_KEYS.get(char)
        if area is None:
            return
        self.pending = {"type": area, "points": list(self.current)}
        if area == "seating":
            self.mode, self.text = "name", ""
        else:
            self._finish()

    def _name_key(self, code: int) -> None:
        if code in ENTER_KEYS:
            seating = sum(1 for s in self.shapes if s["type"] == "seating")
            self.pending["name"] = self.text.strip() or f"Zone {seating + 1}"
            self.mode, self.text = "capacity", ""
        elif code in BACKSPACE_KEYS:
            self.text = self.text[:-1]
        elif 32 <= code < 127 and len(self.text) < MAX_NAME:
            self.text += chr(code)

    def _capacity_key(self, code: int, char: str) -> None:
        if code in ENTER_KEYS:
            value = int(self.text) if self.text.isdigit() and int(self.text) > 0 else DEFAULT_CAPACITY
            self.pending["capacity"] = min(value, 500)
            self._finish()
        elif code in BACKSPACE_KEYS:
            self.text = self.text[:-1]
        elif char.isdigit() and len(self.text) < 3:
            self.text += char

    def _finish(self) -> None:
        shape = self.pending
        self.shapes.append(shape)
        label = shape_label(shape)
        self._reset_pending(f"Added {label}. Draw another area or press S to save.")

    def _reset_pending(self, message: str) -> None:
        self.mode, self.text, self.pending, self.current, self.message = "points", "", {}, [], message

    def load(self, layout: dict[str, Any]) -> None:
        def points(raw: list[list[float]]) -> list[tuple[float, float]]:
            return [(float(x), float(y)) for x, y in raw]

        seating = [
            {
                "type": "seating",
                "name": z["name"],
                "capacity": int(z["capacity"]),
                "points": points(z["points"]),
                "seats": [
                    {"seat_id": str(seat["seat_id"]), "x": float(seat["x"]), "y": float(seat["y"])}
                    for seat in z.get("seats", [])
                ],
            }
            for z in layout.get("zones", [])
        ]
        others = [
            {"type": a["type"], "points": points(a["points"])} for a in layout.get("ignore", []) if a["type"] != "work"
        ]
        raw_work = [*layout.get("work", []), *(a for a in layout.get("ignore", []) if a["type"] == "work")]
        work = [{"type": "work", "area": a["area"], "points": points(a["points"])} for a in raw_work]
        self.shapes = seating + work + others
        loaded = f"Loaded {len(seating)} seating zone(s)"
        if work:
            loaded += f" and {len(work)} work area(s)"
        self.message = f"{loaded}. Edit, or press S to keep them."

    def layout(self) -> dict[str, Any]:
        return {
            "zones": [
                {
                    "name": s["name"],
                    "capacity": len(s["seats"]) if s.get("seats") else s["capacity"],
                    "points": [list(p) for p in s["points"]],
                    **({"seats": [dict(seat) for seat in s["seats"]]} if s.get("seats") else {}),
                }
                for s in self.shapes
                if s["type"] == "seating"
            ],
            "ignore": [
                {"type": s["type"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] not in ("seating", "work")
            ],
            "work": [
                {"area": s["area"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] == "work"
            ],
        }


def shape_label(shape: dict[str, Any]) -> str:
    if shape["type"] == "seating":
        return f"seating zone '{shape['name']}' ({shape['capacity']} seats)"
    if shape["type"] == "work":
        return f"{shape['area']} work area"
    return shape["type"]
