"""Compare known unsupported Windows full-suite failures on two immutable revisions."""

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
    assert len(failed) == 26, f"Known failure count changed: {len(failed)}"
    return failed


root = Path(os.environ["GITHUB_WORKSPACE"])
baseline = failures(root / "baseline")
feature = failures(root / "feature")
assert baseline == feature, (
    f"Feature-only failures: {feature - baseline}; baseline-only: {baseline - feature}"
)
print("The same 26 tests fail on both revisions. This is NOT a passing Windows full suite.")
with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
    summary.write("## Windows full-suite limitation\n\n"
                  "The same 26 failures were reproduced on unchanged upstream and the PR head. "
                  "Native replay/terminal/PowerShell validation runs separately. "
                  "Neither full suite is claimed green.\n")
