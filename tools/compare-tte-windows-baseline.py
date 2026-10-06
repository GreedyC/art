"""Compare known unsupported Windows full-suite failures on two immutable revisions."""

import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def failures(directory):
    result = subprocess.run(
        ["uv", "run", "--frozen", "--group", "dev", "python", "-m", "pytest",
         "-n", "2", "--tb=short", "--junitxml=windows-full-suite.xml"],
        cwd=directory,
        check=False,
    )
    report = ET.parse(directory / "windows-full-suite.xml")
    cases = report.findall(".//testcase")
    errors = [case for case in cases if case.find("error") is not None]
    failed = {
        (case.attrib["classname"], case.attrib["name"])
        for case in cases if case.find("failure") is not None
    }
    assert result.returncode == 1, f"Expected documented failing full suite: {result.returncode}"
    assert not errors, "Unexpected collection or setup errors"
    return failed


def swarm_failures(directory):
    code = """
import json, random, runpy
test = runpy.run_path('tests/effects_tests/test_swarm.py')['test_swarm_coordination_advances_past_area_nine']
failed = []
for seed in range(100):
    random.seed(seed)
    try:
        test(0, '9_swarm_area')
    except AssertionError:
        failed.append(seed)
print(json.dumps(failed))
"""
    result = subprocess.run(
        ["uv", "run", "--frozen", "--group", "dev", "python", "-c", code],
        cwd=directory, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


root = Path(os.environ["GITHUB_WORKSPACE"])
baseline = failures(root / "baseline")
feature = failures(root / "feature")
is_swarm = lambda case: case[0] == "tests.effects_tests.test_swarm" and case[1].startswith(
    "test_swarm_coordination_advances_past_area_nine["
)
stable_baseline = {case for case in baseline if not is_swarm(case)}
stable_feature = {case for case in feature if not is_swarm(case)}
assert len(stable_baseline) == 26, f"Stable baseline failures changed: {stable_baseline}"
assert stable_baseline == stable_feature, (
    f"Feature-only failures: {stable_feature - stable_baseline}; "
    f"baseline-only: {stable_baseline - stable_feature}"
)
for source in ("terminaltexteffects/effects/effect_swarm.py", "tests/effects_tests/test_swarm.py"):
    digest = lambda directory: hashlib.sha256((directory / source).read_bytes()).digest()
    assert digest(root / "baseline") == digest(root / "feature"), f"Swarm source changed: {source}"
base_seeds = swarm_failures(root / "baseline")
feature_seeds = swarm_failures(root / "feature")
assert base_seeds and base_seeds == feature_seeds, (
    f"Seeded Swarm behavior differs: {base_seeds} vs {feature_seeds}"
)
print(f"Same 26 stable failures; same Swarm failing seeds: {base_seeds}")
print("This is NOT a passing Windows full suite.")
with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
    summary.write("## Windows full-suite limitation\n\n"
                  "The same 26 stable failures were reproduced on unchanged upstream and the PR head. "
                  "The unchanged randomized Swarm regression was separately compared across 100 identical seeds. "
                  "Native replay/terminal/PowerShell validation runs separately. "
                  "Neither full suite is claimed green.\n")
