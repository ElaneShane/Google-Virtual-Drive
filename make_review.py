import os
import sys
import collections
from group_detections import read_sightings, build_groups, write_review

run_dir = os.path.expanduser(sys.argv[1])
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

sightings = read_sightings(os.path.join(run_dir, "debug_detections.csv"))
groups = build_groups(sightings, interval)
rows = write_review(groups, os.path.join(run_dir, "review.csv"))

print("sightings:", len(sightings), "-> groups:", len(groups))
print("by tier:", dict(collections.Counter(r["tier"] for r in rows)))
for r in rows:
    print(f"  #{r['group_id']:>2} {r['tier']:<6} {r['label'][:32]:<32} "
          f"x{r['n_sightings']} best {r['best_conf']} frames {r['first_frame']}..{r['last_frame']}")