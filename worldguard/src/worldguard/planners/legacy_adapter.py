"""Explicit blocked adapter: no copied legacy source or silently improved baseline."""


class LegacyAdapter:
    def plan(self, scene_view, task):
        raise RuntimeError("LEGACY_BLOCKED: local source and reuse permission not verified")
