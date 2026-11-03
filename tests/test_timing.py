import unittest

from game.systems.timing import MAX_FRAME_DELTA, clamp_frame_delta


class FrameTimingTests(unittest.TestCase):
    def test_normal_frame_deltas_are_unchanged(self) -> None:
        for frame_rate in (30, 60):
            with self.subTest(frame_rate=frame_rate):
                frame_delta = 1.0 / frame_rate
                self.assertEqual(clamp_frame_delta(frame_delta), frame_delta)

    def test_elapsed_time_is_consistent_at_common_frame_rates(self) -> None:
        simulated_seconds = {
            frame_rate: sum(
                clamp_frame_delta(1.0 / frame_rate)
                for _ in range(frame_rate)
            )
            for frame_rate in (30, 60)
        }

        self.assertAlmostEqual(simulated_seconds[30], 1.0)
        self.assertAlmostEqual(simulated_seconds[60], 1.0)
        self.assertAlmostEqual(simulated_seconds[30], simulated_seconds[60])

    def test_large_frame_delta_is_capped(self) -> None:
        self.assertEqual(clamp_frame_delta(5.0), MAX_FRAME_DELTA)

    def test_negative_frame_delta_is_ignored(self) -> None:
        self.assertEqual(clamp_frame_delta(-0.1), 0.0)


if __name__ == "__main__":
    unittest.main()
