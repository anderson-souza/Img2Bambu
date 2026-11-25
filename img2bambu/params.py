from dataclasses import dataclass, field


@dataclass
class Params:
    width_mm: float = 150.0
    base_mm: float = 10.0
    relief_mm: float = 1.0
    n_colors: int = 3
    min_detail_mm: float = 0.5
    # why: glossy highlights in rendered artwork become thin streaks; 0 disables the filter
    streak_radius_mm: float = 1.0
    background: str = "alpha"          # "alpha" or "color" (flood-fill from corners)
    bg_tolerance: int = 30
    upsample: int = 2
    smooth: int = 0                    # mean-shift level before clustering; 0 disables it
    filaments: int = 0                 # merge closest colors until this many remain; 0 disables it
    protect_lines: bool = False        # keep printable thin lines of every color, not only of outline ones


# (min, max) each Params field accepts, shared by the window, the command line and project files
LIMITS = {
    "bg_tolerance": (1, 120), "n_colors": (2, 8), "filaments": (0, 8), "smooth": (0, 5),
    "min_detail_mm": (0.1, 3.0), "streak_radius_mm": (0.0, 3.0), "width_mm": (10.0, 500.0),
    "base_mm": (1.0, 50.0), "relief_mm": (0.2, 10.0),
}


@dataclass
class Palette:
    colors: list                        # list of (r, g, b) ints, index = label
    base_index: int = 0
    merges: dict = field(default_factory=dict)   # label -> label it is merged into
    streak: set = field(default_factory=set)     # labels that get the highlight-streak filter
    # invariant: a label is never in both outline and streak
    outline: set = field(default_factory=set)    # labels whose thin lines are kept and widened to print
    # invariant: samples[i] ("cor na imagem") decides which pixels go to label i; colors[i] is the filament
    samples: list = field(default_factory=list)
    edited: set = field(default_factory=set)     # labels whose sample or filament the user changed

    def resolve(self, label):
        seen = set()
        while label in self.merges and label not in seen:
            seen.add(label)
            label = self.merges[label]
        return label

    def active(self):
        return [i for i in range(len(self.colors)) if self.resolve(i) == i]

    def set_streak(self, label, on):
        (self.streak.add if on else self.streak.discard)(label)
        if on:
            self.outline.discard(label)

    def set_outline(self, label, on):
        (self.outline.add if on else self.outline.discard)(label)
        if on:
            self.streak.discard(label)

    def merge(self, label, target):
        """Merges `label` into `target` (None undoes it); False, with nothing changed, if it would form a cycle."""
        before = self.merges.pop(label, None)
        ok = target is None or self.resolve(target) != label
        if not ok:
            target = before
        if target is not None:
            self.merges[label] = target
        self.base_index = self.resolve(self.base_index)
        return ok


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[int(c) for c in rgb])
