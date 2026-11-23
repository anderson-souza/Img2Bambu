from img2bambu.history import History


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def run(changes, start=150, **kw):
    """changes: (seconds since the previous one, key, value); label = key."""
    clock = Clock()
    h, cur = History(clock=clock, **kw), start
    for dt, key, value in changes:
        clock.t += dt
        h.record(key, cur, value, key)
        cur = value
    return h


def test_run_on_one_field_is_one_step_back_to_its_start():
    h = run([(5, "w", 155), (0.9, "w", 160), (0.9, "w", 165)])
    assert h.undo() == ("w", 150)
    assert h.undo() is None


def test_exactly_one_second_splits_the_run():
    h = run([(5, "w", 155), (1.0, "w", 160)])
    assert [h.undo(), h.undo(), h.undo()] == [("w", 155), ("w", 150), None]


def test_another_field_splits_the_run():
    h = run([(5, "w", 1), (0.1, "r", 2), (0.1, "w", 3)], start=0)
    assert [h.undo(), h.undo(), h.undo()] == [("w", 2), ("r", 1), ("w", 0)]


def test_no_key_never_groups():
    h = run([(5, None, 1), (0.1, None, 2)], start=0)
    assert len(h.steps) == 2


def test_run_back_to_start_leaves_no_step_but_keeps_older_ones():
    h = run([(5, "r", 150), (5, "w", 155), (0.1, "w", 150)], start=140)
    assert [h.undo(), h.undo()] == [("r", 140), None]
    h = run([(5, "w", 155), (0.1, "w", 150), (0.1, "w", 160)])
    assert [h.undo(), h.undo()] == [("w", 150), None]


def test_undo_ends_the_run():
    h = run([(5, "w", 1), (5, "w", 2)], start=0)
    h.undo()
    h.record("w", 1, 3, "w")
    assert [h.undo(), h.undo()] == [("w", 1), ("w", 0)]


def test_limit_drops_the_oldest():
    h = run([(5, "w", i) for i in range(1, 52)], start=0)
    got = [h.undo() for _ in range(51)]
    assert got[0] == ("w", 50) and got[49] == ("w", 1) and got[50] is None


def test_unchanged_state_is_no_step_and_clear_empties():
    h = run([(5, "w", 150)])
    assert h.undo() is None
    h = run([(5, "w", 151)])
    h.clear()
    h.record("w", 151, 152, "w")
    assert [h.undo(), h.undo()] == [("w", 151), None]
