# Check: Aqua over DCU against Heavens-Above

**What:** our predicted passes (`passes.csv`, run of 28 Oct 2026 20:24 UTC, TLE epoch 28 Oct 13:44 UTC) compared
with an independent prediction from Heavens-Above for the same satellite (27424) and place
(53.385° N, 6.2565° W, 60 m), fetched 28 Oct 2026.
Source: https://www.heavens-above.com/PassSummary.aspx?satid=27424&lat=53.385&lng=-6.2565&loc=DCU&alt=60&tz=UCT

Heavens-Above lists only *visible* passes (satellite sunlit, sky dark) that reach at least 10°, and gives
elevations to the nearest degree.  A pass "ends" there either at 10° or when the satellite enters Earth's shadow.

| Pass (UTC) | Highest point, ours | Highest point, Heavens-Above | Enters shadow, ours | Heavens-Above end |
|---|---|---|---|---|
| 29 Oct, pass 2  | 04:35:43, 59.7°, az 101° (ESE) | 04:35:44, 60°, ESE | 04:39:13 | 04:39:13, 17° |
| 29 Oct, pass 3  | 06:12:48, 24.5°, az 302° (WNW) | 06:12:48, 25°, WNW | (sets at 0° 06:19:06) | 06:16:32, 10° |
| 30 Oct, pass 9  | 03:35:31, 19.6°, az 90° (E)    | 03:35:30, 20°, E   | 03:38:36 | 03:38:33, 11° |
| 30 Oct, pass 10 | 05:13:22, 68.5°, az 290° (WNW) | 05:13:21, 68°, WNW | 05:17:07 | 05:17:04, 16° |
| 31 Oct, pass 18 | 04:13:25, 38.6°, az 96° (E)    | 04:13:26, 39°, E   | 04:16:25 | 04:16:24, 18° |
| 31 Oct, pass 19 | 05:50:50, 34.9°, az 296° (WNW) | 05:50:48, 35°, WNW | 05:55:00 | 05:54:55, 11° |

**Result:** times of the highest point agree to within 2 s, elevations to within 0.5°, directions match, and the
moment the satellite enters Earth's shadow agrees to within 5 s (our sampling step).  Our other visible passes
(passes 1, 16, 17: highest 9.2°, 2.8°, 4.8°) do not reach 10°, so Heavens-Above correctly leaves them out.

Heavens-Above also predicts magnitudes of 3.7 – 6.2 for these passes; that is a separate model of brightness and
is not compared here (our brightness for real passes is the next step).
