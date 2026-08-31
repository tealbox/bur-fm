#!/usr/bin/env python3
"""Compare FortiGate-like config files and print patch-ready deviations.

The script reads a gold-standard config and compares it with another config.
It converts the diff into a config-style patch that can be applied back to a
device, keeping the same `config ...`, `edit ...`, `set ...`, `next`, `end`
format.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union


def normalize_config_data(config: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
    """Accept raw config text or a nested dict and always return a parsed dict."""
    if config is None:
        return {}
    if isinstance(config, dict):
        return deepcopy(config)
    if isinstance(config, str):
        return parse_config(config)
    raise TypeError(f"Unsupported config type: {type(config).__name__}")


def diff_widget_config(reference: Union[str, Dict[str, Any]], candidate: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare two config snippets that are expected to be under 'config widget'.

    This helper accepts raw config text or a parsed dict and returns the config diff.
    It is designed for a golden/config-compare workflow where only the widget block is checked.
    """
    ref_cfg = normalize_config_data(reference)
    cand_cfg = normalize_config_data(candidate)
    return compare_configs(ref_cfg, cand_cfg)


def config_diff(reference: Union[str, Dict[str, Any]], candidate: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare two config objects or raw config snippets and return a diff list."""
    return diff_widget_config(reference, candidate)


def parse_config(text: str) -> Dict[str, Any]:
    """Parse a FortiGate-like config into a nested dict.

    Empty content returns an empty dict.
    """
    if text is None:
        return {}

    stripped = text.strip()
    if not stripped:
        return {}

    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]

    def parse_block(index: int) -> Tuple[Dict[str, Any], int]:
        block: Dict[str, Any] = {}

        while index < len(lines):
            raw = lines[index].strip()
            if not raw:
                index += 1
                continue

            lower = raw.lower()
            if lower in {"end", "next"}:
                return block, index + 1

            if lower.startswith("config "):
                section = raw.split(None, 1)[1].strip()
                child, index = parse_block(index + 1)
                key = f"config {section}"
                block[key] = child
                continue

            if lower.startswith("edit "):
                name = raw.split(None, 1)[1].strip()
                child, index = parse_block(index + 1)
                block[f"edit {name}"] = child
                continue

            if lower.startswith("set "):
                parts = raw.split(None, 2)
                if len(parts) >= 3:
                    key = parts[1]
                    value = parts[2].strip()
                else:
                    key = parts[1]
                    value = ""
                block[key] = value
                index += 1
                continue

            index += 1

        return block, index

    root, _ = parse_block(0)
    return root


def edit_config(config: Dict[str, Any], path: List[str], value: Any) -> Dict[str, Any]:
    """Return a new dict with one value replaced.

    Example:
        cfg = edit_config(cfg, ['config system admin', 'edit "acunoc01"', 'accprofile'], '"read_only"')
    """
    updated = deepcopy(config)
    cursor: Dict[str, Any] = updated

    for part in path[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]

    cursor[path[-1]] = value
    return updated


def flatten_dict(node: Dict[str, Any], path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    """Flatten nested config dict into (path_tuple, value) entries."""
    flat: List[Tuple[Tuple[str, ...], Any]] = []

    for key, value in node.items():
        current_path = path + (key,)
        if isinstance(value, dict):
            flat.extend(flatten_dict(value, current_path))
        else:
            flat.append((current_path, value))

    return flat


def compare_configs(reference: Dict[str, Any], candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compare the gold standard and candidate config and return a list of diffs."""
    ref_map = {path: value for path, value in flatten_dict(reference)}
    cand_map = {path: value for path, value in flatten_dict(candidate)}

    diff: List[Dict[str, Any]] = []
    all_paths = sorted(set(ref_map) | set(cand_map), key=lambda item: "|".join(item))

    for path in all_paths:
        in_ref = path in ref_map
        in_cand = path in cand_map

        if not in_ref:
            diff.append({
                "path": list(path),
                "state": "missing_in_reference",
                "actual": cand_map[path],
            })
            continue

        if not in_cand:
            diff.append({
                "path": list(path),
                "state": "missing_in_candidate",
                "expected": ref_map[path],
            })
            continue

        if ref_map[path] != cand_map[path]:
            diff.append({
                "path": list(path),
                "state": "changed",
                "expected": ref_map[path],
                "actual": cand_map[path],
            })

    return diff


def render_path_as_config(path: List[str], value: Any) -> List[str]:
    """Convert a path like ['config system admin','edit "acunoc01"','trusthost1']
    into config-style patch lines.
    """
    lines: List[str] = []
    indent = 0

    for segment in path[:-1]:
        if segment.startswith("config "):
            lines.append(f"{' ' * indent}{segment}")
            indent += 4
        elif segment.startswith("edit "):
            lines.append(f"{' ' * indent}{segment}")
            indent += 4
        else:
            lines.append(f"{' ' * indent}{segment}")
            indent += 4

    lines.append(f"{' ' * indent}set {path[-1]} {value}")

    for segment in reversed(path[:-1]):
        if segment.startswith("config "):
            indent -= 4
            lines.append(f"{' ' * indent}end")
        elif segment.startswith("edit "):
            indent -= 4
            lines.append(f"{' ' * indent}next")

    return lines


def render_diff_as_config(diff: List[Dict[str, Any]]) -> List[str]:
    """Render deviations as patch-ready config lines."""
    lines: List[str] = []

    for item in diff:
        path = item["path"]
        state = item["state"]

        if state == "changed":
            lines.append(f"# changed: {'/'.join(path)} expected={item['expected']} actual={item['actual']}")
            lines.extend(render_path_as_config(path, item["actual"]))
        elif state == "missing_in_candidate":
            lines.append(f"# missing: {'/'.join(path)} expected={item['expected']}")
            lines.extend(render_path_as_config(path, item["expected"]))
        elif state == "missing_in_reference":
            lines.append(f"# extra: {'/'.join(path)} actual={item['actual']}")
        else:
            lines.append(f"# unknown diff: {'/'.join(path)}")

        lines.append("")

    return lines


def load_config_file(path: str | Path) -> Dict[str, Any]:
    """Read a config file and return the parsed dict."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return parse_config(text)


def write_log(path: str | Path, lines: Iterable[str]) -> None:
    target = Path(path)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _test_cases() -> None:
    """Simple regression tests for empty configs and widget edit blocks."""
    assert diff_widget_config("", "") == []

    ref_empty = "config widget\n    edit 1\n        set type fortiview\n    next\nend\n"
    cand_empty = "config widget\n    edit 1\n        set type fortiview\n    next\nend\n"
    assert diff_widget_config(ref_empty, cand_empty) == []

    ref_widget = """
config widget
    edit 1
        set type fortiview
        set width 2
    next
end
"""
    cand_widget = """
config widget
    edit 1
        set type fortiview
        set width 3
    next
end
"""
    changes = diff_widget_config(ref_widget, cand_widget)
    assert any(item["state"] == "changed" and item["path"][-1] == "width" for item in changes)

    ref_widget_missing = "config widget\n    edit 1\n        set type fortiview\n    next\nend\n"
    cand_widget_missing = "config widget\nend\n"
    changes = diff_widget_config(ref_widget_missing, cand_widget_missing)
    assert any(item["state"] == "missing_in_candidate" for item in changes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check config deviation against a gold-standard file.")
    parser.add_argument("gold", help="Gold-standard config file")
    parser.add_argument("candidate", help="Candidate config file to compare")
    parser.add_argument("-o", "--output", help="Optional log file for diffs")
    args = parser.parse_args()

    gold_cfg = load_config_file(args.gold)
    candidate_cfg = load_config_file(args.candidate)
    diff = compare_configs(gold_cfg, candidate_cfg)

    if not diff:
        print("No config differences found.")
        if args.output:
            write_log(args.output, ["No config differences found."])
        return

    patch_lines = render_diff_as_config(diff)
    print("\n".join(patch_lines))

    if args.output:
        write_log(args.output, patch_lines)


if __name__ == "__main__":
    _test_cases()
    main()
