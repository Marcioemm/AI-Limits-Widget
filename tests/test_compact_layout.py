import unittest

from ai_limits_widget.compact_layout import (
    anchored_window_y,
    animation_easing,
    compact_grid_position,
    should_expand_upward,
)


class CompactAnimationTests(unittest.TestCase):
    def test_upward_expansion_starts_without_a_large_jump(self) -> None:
        first_frame = 16 / 220
        upward = animation_easing(first_frame, expanding=True, upward=True)
        downward = animation_easing(first_frame, expanding=True, upward=False)

        self.assertLess(upward, 0.02)
        self.assertGreater(downward, 0.15)
        self.assertLess(upward, downward)

    def test_easing_is_clamped_and_reaches_both_ends(self) -> None:
        self.assertEqual(0.0, animation_easing(-1, expanding=True, upward=True))
        self.assertEqual(1.0, animation_easing(2, expanding=True, upward=True))


class CompactDirectionTests(unittest.TestCase):
    def test_expands_down_when_there_is_enough_space(self) -> None:
        self.assertFalse(should_expand_upward(300, 100, 48, 0, 900))

    def test_expands_up_when_bottom_would_cut_details(self) -> None:
        self.assertTrue(should_expand_upward(300, 840, 48, 0, 900))

    def test_respects_monitor_with_negative_top_coordinate(self) -> None:
        self.assertTrue(should_expand_upward(320, -80, 48, -900, 900))

    def test_chooses_side_with_more_room_when_neither_side_fits(self) -> None:
        self.assertTrue(should_expand_upward(700, 100, 48, 0, 200))
        self.assertFalse(should_expand_upward(700, 20, 48, 0, 200))


class CompactGeometryTests(unittest.TestCase):
    def test_top_anchor_keeps_window_y(self) -> None:
        self.assertEqual(400, anchored_window_y(400, 48, 300, anchor_bottom=False))

    def test_bottom_anchor_keeps_window_bottom(self) -> None:
        new_y = anchored_window_y(400, 48, 300, anchor_bottom=True)
        self.assertEqual(148, new_y)
        self.assertEqual(448, new_y + 300)

    def test_extra_grid_rows_are_added_above_primary_row(self) -> None:
        positions = [compact_grid_position(index, 2, 3, upward=True) for index in range(3)]
        self.assertEqual([(1, 0), (1, 1), (0, 0)], positions)

    def test_grid_rows_keep_normal_order_when_expanding_down(self) -> None:
        positions = [compact_grid_position(index, 2, 3, upward=False) for index in range(3)]
        self.assertEqual([(0, 0), (0, 1), (1, 0)], positions)

    def test_invalid_grid_arguments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compact_grid_position(0, 0, 1, upward=False)
        with self.assertRaises(IndexError):
            compact_grid_position(2, 1, 1, upward=False)


if __name__ == "__main__":
    unittest.main()
