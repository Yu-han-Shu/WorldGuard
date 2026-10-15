from typing import Protocol

from worldguard.contracts import PlanResult, Scene, Task


class NavigationAdapter(Protocol):
    def plan(self, scene_view: Scene, task: Task) -> PlanResult: ...
