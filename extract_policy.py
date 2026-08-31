#!/usr/bin/env python3
import re
import argparse
from datetime import datetime
from pathlib import Path


def process_file(in_path: Path, out_path: Path):
    lines = in_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    start_idx = None
    for i, line in enumerate(lines):
        if "config firewall policy" in line.lower():
            start_idx = i
            break

    if start_idx is None:
        raise SystemExit(f"No 'config firewall policy' section found in {in_path}")

    # collect until next 'end' line (exclusive)
    collected = []
    for line in lines[start_idx:]:
        if line.strip().lower() == "end":
            break
        collected.append(line)

    processed = []
    # edit line for exactly 10 digits
    edit_10_re = re.compile(r'^(?P<indent>\s*)edit\s+(?P<num>\d{10})(?P<rest>.*)$', re.IGNORECASE)
    edit_any_re = re.compile(r'^(?P<indent>\s*)edit\s+(?P<num>\S+)(?P<rest>.*)$', re.IGNORECASE)

    valid_10_digit_blocks = 0
    other_edit_blocks = 0

    i = 0
    n = len(collected)
    while i < n:
        line = collected[i]
        m10 = edit_10_re.match(line)
        many = edit_any_re.match(line)

        if many:
            if m10:
                valid_10_digit_blocks += 1
                indent = m10.group('indent') or ''
                rest = m10.group('rest') or ''
                processed.append(f"{indent}edit 0{rest}\n")
                i += 1
                while i < n:
                    cur = collected[i]
                    stripped = cur.lstrip()
                    if stripped.lower().startswith("set uuid") or stripped.lower().startswith("set online"):
                        processed.append("# " + cur)
                    else:
                        processed.append(cur)
                    i += 1
                    if cur.strip().lower() == 'next':
                        break
                continue
            else:
                other_edit_blocks += 1
                i += 1
                while i < n:
                    if collected[i].strip().lower() == 'next':
                        i += 1
                        break
                    if edit_any_re.match(collected[i]):
                        break
                    i += 1
                continue

        stripped = line.lstrip()
        if stripped.lower().startswith("set uuid") or stripped.lower().startswith("set online"):
            processed.append("# " + line)
        else:
            processed.append(line)
        i += 1

    out_path.write_text(''.join(processed), encoding="utf-8")
    return {
        "output_path": out_path,
        "valid_10_digit_blocks": valid_10_digit_blocks,
        "other_edit_blocks": other_edit_blocks,
    }


def main():
    p = argparse.ArgumentParser(description="Extract and sanitize 'config firewall policy' from a FortiGate-like .conf file")
    p.add_argument('input', help='Path to input .conf')
    p.add_argument('-o', '--output', help='Path to output file (optional)')
    args = p.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    if args.output:
        out_path = Path(args.output)
    else:
        stamp = datetime.now().strftime('%Y%m%d')
        out_path = in_path.with_name(f"{in_path.stem}_{stamp}.conf")

    result = process_file(in_path, out_path)
    print(f"Wrote extracted policy to: {result['output_path']}")
    print(f"Summary: 10-digit edit sections = {result['valid_10_digit_blocks']}; other edit sections = {result['other_edit_blocks']}")


if __name__ == '__main__':
    main()
