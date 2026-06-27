"""ToolGraph — track inter-tool dependencies and analyze tool change impact."""

from typing import Any

_dependencies: dict[str, list[str]] = {}  # caller -> [callee]


def add_dependency(caller: str, callee: str) -> None:
    _dependencies.setdefault(caller, []).append(callee)


def remove_dependency(caller: str, callee: str) -> None:
    deps = _dependencies.get(caller, [])
    if callee in deps:
        deps.remove(callee)


def get_dependencies(tool_id: str) -> list[str]:
    """Tools that `tool_id` depends on (direct callees)."""
    return _dependencies.get(tool_id, [])


def get_dependents(tool_id: str) -> list[str]:
    """Tools that depend on `tool_id` (direct callers)."""
    return [caller for caller, deps in _dependencies.items() if tool_id in deps]


def analyze_impact(tool_id: str) -> dict:
    """Analyze what would break if `tool_id` changes or is removed."""
    dependents = get_dependents(tool_id)
    transitive: set[str] = set()
    queue = list(dependents)
    while queue:
        current = queue.pop(0)
        if current in transitive:
            continue
        transitive.add(current)
        for dep in get_dependents(current):
            if dep not in transitive:
                queue.append(dep)

    return {
        "tool_id": tool_id,
        "direct_dependents": dependents,
        "transitive_dependents": sorted(transitive - set(dependents)),
        "total_affected": len(dependents) + len(transitive),
    }


def clear() -> None:
    _dependencies.clear()
