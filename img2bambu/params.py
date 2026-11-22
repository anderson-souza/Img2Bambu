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


@dataclass
class Palette:
    colors: list                        # list of (r, g, b) ints, index = label
    base_index: int = 0
    merges: dict = field(default_factory=dict)   # label -> label it is merged into
    streak: set = field(default_factory=set)     # labels that get the highlight-streak filter
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


def carry_over(old, new):
    """New palette from a re-analysis, keeping the user's edited rows of the same image."""
    if old is None:
        return new
    for i in old.edited:
        if i < len(new.colors):
            new.colors[i], new.samples[i] = old.colors[i], old.samples[i]
            new.edited.add(i)
    return new


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[int(c) for c in rgb])
