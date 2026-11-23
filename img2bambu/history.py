import time
from dataclasses import dataclass

from .params import Palette


@dataclass
class Snapshot:
    values: list                       # numeric fields, in window order
    palette: Palette | None
    analysis: object
    pending: bool                      # a detection was running, so palette/analysis predate `values`

    def __eq__(self, o):
        # why: an Analysis holds arrays, which have no plain ==
        return (self.values == o.values and self.palette == o.palette and self.analysis is o.analysis
                and self.pending == o.pending)


class History:
    """Undo steps as snapshots of the state before each change; snapshots only need ==."""

    def __init__(self, limit=50, gap=1.0, clock=time.monotonic):
        self.limit, self.gap, self.clock = limit, gap, clock
        self.clear()

    def clear(self):
        self.steps = []                # (label, state before), oldest first
        self.burst = None              # (key, time) of the last change, None once its run is over

    def record(self, label, before, after, key=None):
        """Changes sharing a `key` less than `gap` seconds apart are one step; key=None never groups."""
        if before == after:
            return
        now = self.clock()
        joins = key is not None and self.burst is not None and self.burst[0] == key and now - self.burst[1] < self.gap
        self.burst = (key, now)
        if not joins:
            self.steps.append((label, before))
            del self.steps[:-self.limit]
        elif self.steps[-1][1] == after:     # why: the run came back to where it started
            self.steps.pop()
            self.burst = None

    def undo(self):
        """Pops the newest (label, state to restore), or None."""
        self.burst = None
        return self.steps.pop() if self.steps else None
