from geo import distance_m

# PLACEHOLDER numbers. We will pick real ones from the baseline run on all clips.
MIN_EXCESS_M = 4.0       # never flag a hop that is off by less than this many meters
ERROR_MULTIPLIER = 2.0   # allow more slack when the camera says its GPS error is big


def check_hops(gps):
    """gps rows are (video_t, utc_t, lat, lon, mode, h_error, speed_mps).
    For each hop between two neighbouring points, compare how far the position
    moved with how far the camera's own speed says it should have moved."""
    results = []
    for prev, cur in zip(gps, gps[1:]):
        t, h_error, speed_mps = cur[0], cur[5], cur[6]
        dt = t - prev[0]
        if dt <= 0:
            continue

        if dt > 2.0:
            continue    # points are too far apart in time for the speed check to mean anything
        hop_m = distance_m(prev[2], prev[3], cur[2], cur[3])

        if speed_mps is None:
            results.append({"t": t, "start_t": prev[0], "hop_m": hop_m, "excess_m": None,
                            "flagged": False, "reason": "no camera speed, could not check"})
            continue

        expected_m = speed_mps * dt                  # distance the camera's speed predicts
        excess_m = abs(hop_m - expected_m)           # how far off the position is
        allowed_m = max(MIN_EXCESS_M, ERROR_MULTIPLIER * (h_error or 0))
        flagged = excess_m > allowed_m
        reason = (f"moved {hop_m:.1f} m but camera speed predicts {expected_m:.1f} m"
                  if flagged else "ok")
        results.append({"t": t, "start_t": prev[0], "hop_m": hop_m, "excess_m": excess_m,
                "flagged": flagged, "reason": reason})
    return results

def find_bad_points(gps, hop_results, max_gap_s=2.0):
    """Decide WHICH point of each flagged hop is the bad one.
    Returns (bad, questionable): two sets of video times."""
    flagged = [r for r in hop_results if r["flagged"]]
    flagged_start_times = {r["start_t"] for r in flagged}   # hops that leave a point

    # points that begin a new stretch: the first point, or the first after a dropout
    first_after_gap = {gps[0][0]}
    for prev, cur in zip(gps, gps[1:]):
        if cur[0] - prev[0] > max_gap_s:
            first_after_gap.add(cur[0])

    bad = set()
    questionable = set()
    for r in flagged:
        start, end = r["start_t"], r["t"]
        if start in bad or end in bad:
            continue                        # already explained by a bad point we found
        if end in flagged_start_times:
            bad.add(end)                    # rule 1: hops on both sides are flagged
        elif start in first_after_gap:
            bad.add(start)                  # rule 2: first reading after a dropout
        else:
            questionable.add(end)           # rule 3: can't tell which end is wrong
    return bad, questionable