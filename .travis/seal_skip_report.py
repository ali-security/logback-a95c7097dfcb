#!/usr/bin/env python3
"""Print a per-test skip report and test totals from surefire XML reports.

logback runs surefire with <parallel>classes</parallel>, so the console
"Tests run: ... Skipped: N ... in <Class>" lines can attribute a skip to the
wrong class. The testcase classname inside each TEST-*.xml is correct, so this
report lists every skipped test by its real class with the reason (the skip
message, or the @Disabled / assume line quoted from the test source), grouped
one line per reason, followed by per-module and overall totals.
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict


def source_reason(module, classname, method):
    path = os.path.join(module, "src", "test", "java", *classname.split("$")[0].split(".")) + ".java"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    # method-level annotation: scan back from the method declaration
    decl = re.compile(r"\b(void|public|private|protected)\b.*\b" + re.escape(method.split("(")[0].split("[")[0]) + r"\s*\(")
    for i, line in enumerate(lines):
        if decl.search(line):
            for j in range(i - 1, max(i - 8, -1), -1):
                s = lines[j].strip()
                if s.startswith("@Disabled") or s.startswith("@Ignore"):
                    return "method " + s
                if s.endswith(";") or s.endswith("}") or s.endswith("{"):
                    break
            for j in range(i, min(i + 15, len(lines))):
                s = lines[j].strip()
                if "assume" in s.lower() and "(" in s:
                    return "assumption not met: " + s
            break
    for i, line in enumerate(lines):
        if re.match(r"\s*(public\s+|abstract\s+|final\s+)*class\s", line):
            for j in range(i - 1, max(i - 8, -1), -1):
                s = lines[j].strip()
                if s.startswith("@Disabled") or s.startswith("@Ignore"):
                    return "class " + s
            break
    return None


def main(modules):
    groups = OrderedDict()
    totals = []
    for module in modules:
        run = fail = err = skip = 0
        for report in sorted(glob.glob(os.path.join(module, "target", "surefire-reports", "TEST-*.xml"))):
            root = ET.parse(report).getroot()
            for case in root.iter("testcase"):
                run += 1
                if case.find("failure") is not None:
                    fail += 1
                elif case.find("error") is not None:
                    err += 1
                sk = case.find("skipped")
                if sk is not None:
                    skip += 1
                    cls = case.get("classname", "?")
                    name = case.get("name", "?")
                    msg = (sk.get("message") or "").strip()
                    reason = msg or source_reason(module, cls, name) or "skipped by JUnit with no message (no @Disabled/assume found in source)"
                    if reason == msg:
                        reason = "message: " + msg
                    groups.setdefault(reason, []).append(cls.rsplit(".", 1)[-1] + "#" + name)
        totals.append((module, run, fail, err, skip))
    print("=" * 72)
    print("SKIPPED TESTS (by real testcase class; one line per reason)")
    print("NOTE: surefire <parallel>classes</parallel> can attribute skips to the wrong class in console lines;")
    print("      the classnames below come from each <testcase> in TEST-*.xml and are correct.")
    for reason, tests in groups.items():
        print("SKIP [%d] %s -> %s" % (len(tests), reason, ", ".join(tests)))
    print("-" * 72)
    grand = [0, 0, 0, 0]
    for module, run, fail, err, skip in totals:
        print("MODULE %-28s run=%d passed=%d failures=%d errors=%d skipped=%d" % (module, run, run - fail - err - skip, fail, err, skip))
        for k, v in enumerate((run, fail, err, skip)):
            grand[k] += v
    run, fail, err, skip = grand
    print("TOTAL tests run=%d passed=%d failures=%d errors=%d skipped=%d" % (run, run - fail - err - skip, fail, err, skip))
    print("=" * 72)
    return 1 if (fail or err or run == 0) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
