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
    simplify_mm: float = 0.04
    smooth: int = 0                    # mean-shift level before clustering; 0 disables it
    filaments: int = 0                 # merge closest colors until this many remain; 0 disables it
    protect_lines: bool = False        # keep printable thin lines of every color, not only of outline ones


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


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[int(c) for c in rgb])
