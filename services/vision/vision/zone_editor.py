from dataclasses import dataclass, field
from typing import Any, Literal

ENTER_KEYS = {10, 13}
BACKSPACE_KEYS = {8, 127}
ESCAPE = 27
AREA_KEYS = {"s": "seating", "q": "queue", "w": "walkway", "i": "ignore"}
DEFAULT_CAPACITY = 4
MAX_NAME = 40

Mode = Literal["points", "type", "name", "capacity"]
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

    def click(self, x: int, y: int) -> None:
        if self.mode != "points":
            return
        nx = min(max(x / self.width, 0.0), 1.0)
        ny = min(max(y / self.height, 0.0), 1.0)
        self.current.append((round(nx, 4), round(ny, 4)))
        self.message = ""

    def prompt(self) -> str:
        if self.mode == "type":
            return "Area type: S seating, Q queue, W walkway, I ignore (Esc cancels)"
        if self.mode == "name":
            return f"Zone name: {self.text}_   (Enter to continue)"
        if self.mode == "capacity":
            return f"Seats in this zone: {self.text}_   (Enter, blank = {DEFAULT_CAPACITY})"
        if self.message:
            return self.message
        return "Click corners of an area, Enter to close it, U undo, Esc clear, S save, Q quit"

    def key(self, code: int) -> Action:
        if code < 0 or code == 255:
            return None
        char = chr(code).lower() if 32 <= code < 127 else ""
        if self.mode == "points":
            return self._points_key(code, char)
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
        elif char == "s":
            if not any(s["type"] == "seating" for s in self.shapes):
                self.message = "Add at least one seating zone before saving."
                return None
            return "save"
        elif code == ESCAPE:
            self.current = []
            self.message = "Cleared the shape in progress."
        elif char == "q":
            return "quit"
        return None

    def _type_key(self, char: str) -> None:
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
        label = (
            f"seating zone '{shape['name']}' ({shape['capacity']} seats)"
            if shape["type"] == "seating"
            else shape["type"]
        )
        self._reset_pending(f"Added {label}. Draw another area or press S to save.")

    def _reset_pending(self, message: str) -> None:
        self.mode, self.text, self.pending, self.current, self.message = "points", "", {}, [], message

    def layout(self) -> dict[str, Any]:
        return {
            "zones": [
                {"name": s["name"], "capacity": s["capacity"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] == "seating"
            ],
            "ignore": [
                {"type": s["type"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] != "seating"
            ],
        }
