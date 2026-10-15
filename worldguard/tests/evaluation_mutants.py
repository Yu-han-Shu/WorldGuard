"""TEST_MUTANT fixture only. Not a discovered defect in the legacy repository.

The controlled mutant deliberately gives the reference planner the pre-fault map.
The navigation algorithm itself remains unchanged. Runtime product names this a stale-view test.
"""

METHODS = {"reference_current": False, "TEST_MUTANT_stale_view": True}
