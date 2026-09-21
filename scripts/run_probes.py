import shutil
import tempfile
import json
import sys
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent

with tempfile.TemporaryDirectory() as td:
    disp = Path(td) / "voltpulse_disposable"
    print(f"Creating disposable copy at: {disp}")
    shutil.copytree(root, disp, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "data", "results", "*.pyc", "index.html"))

    probe_doc = (root / "audit" / "EXTERNAL_REVIEW_REPORT.md").read_text(encoding="utf-8")
    start_tag = '"""Independent audit probes.'
    start_idx = probe_doc.find(start_tag)
    end_idx = probe_doc.find("```", start_idx)
    probe_script = probe_doc[start_idx:end_idx].strip()

    probe_file = Path(td) / "probes.py"
    probe_file.write_text(probe_script, encoding="utf-8")

    out_json = Path(td) / "probe_results.json"

    print("Running independent probe script on disposable project...")
    env = dict(shutil.os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(probe_file), str(disp), str(out_json)],
        capture_output=True,
        text=True,
        env=env
    )

    print("--- STDOUT ---")
    print(proc.stdout)
    print("--- STDERR ---")
    print(proc.stderr)
    print("Exit code:", proc.returncode)

    if out_json.exists():
        results = json.loads(out_json.read_text(encoding="utf-8"))
        print("\n--- VERIFICATION OF PROBES ---")
        # 1. Synthetic
        syn = results.get("synthetic", {})
        print("Probe 1 (Synthetic Data Detection):")
        print("  all_1344_records_equal:", syn.get("all_1344_records_equal"))
        print("  raw_96_prices_equal:", syn.get("raw_96_prices_equal"))
        print("  processed_96_prices_equal:", syn.get("processed_96_prices_equal"))
        print("  raw_hash_matches_metadata:", syn.get("raw_hash_matches_metadata"))

        # 2. QC
        qc = results.get("qc_invalid_inputs_accepted", {})
        print("Probe 2 (QC Invalid Inputs Accepted - all must be False):")
        for k, v in qc.items():
            status = "PASS (Rejected)" if v is False else "FAIL (Accepted!)"
            print(f"  {k}: {v} -> {status}")

        # 3. Raw archive
        rev_files = results.get("raw_revision_files", [])
        rev_content = results.get("raw_revision_content", "")
        print("Probe 3 (Raw Archive Immutable Revision):")
        print(f"  Content of original.csv: '{rev_content}' (Expected: 'first' -> {'PASS' if rev_content == 'first' else 'FAIL'})")
        print(f"  Revision files: {rev_files}")

        # 4. Model & Terminal SOC
        short_soc = results.get("short_window_terminal_soc")
        print(f"Probe 4 (Short Window Terminal SOC): {short_soc} (Expected: 0.50 -> {'PASS' if short_soc == 0.50 else 'FAIL'})")

        # 5. Half-day and mixed
        half = results.get("half_day_backtested_rows")
        mixed = results.get("mixed_da_rt_result_rows")
        print(f"Probe 5 (Half Day Rows): {half} (Expected: 0 -> {'PASS' if half == 0 else 'FAIL'})")
        print(f"Probe 5 (Mixed DA/RT Rows): {mixed} (Expected: 0 -> {'PASS' if mixed == 0 else 'FAIL'})")

        # 6. Fixture pipeline sandbox isolation
        fp = results.get("fixture_pipeline", {})
        print("Probe 6 (Fixture Pipeline Sandbox Isolation):")
        print(f"  Exit code: {fp.get('exit')} (Expected: 0)")
        print(f"  Production parquet exists: {fp.get('production_parquet_exists')} (Expected: False -> {'PASS' if not fp.get('production_parquet_exists') else 'FAIL'})")
        print(f"  Public html exists: {fp.get('public_html_exists')} (Expected: False -> {'PASS' if not fp.get('public_html_exists') else 'FAIL'})")

        # 7. Live download failure handling
        live_fail = results.get("all_downloads_failed", {})
        print("Probe 7 (All Live Downloads Failed):")
        print(f"  Exit code: {live_fail.get('exit')} (Expected: 1 -> {'PASS' if live_fail.get('exit') == 1 else 'FAIL'})")
        print(f"  Status beacon: {live_fail.get('status', {}).get('status')} (Expected: 'failed' -> {'PASS' if live_fail.get('status', {}).get('status') == 'failed' else 'FAIL'})")

        # 8. Acceptance dynamic reporting
        acc = results.get("acceptance_all_commands_failed", {})
        print("Probe 8 (Acceptance Dynamic Reporting When Commands Fail):")
        print(f"  Exit code: {acc.get('exit')} (Expected: 1 -> {'PASS' if acc.get('exit') == 1 else 'FAIL'})")
        print(f"  Says release eligible: {acc.get('state_says_release_eligible')} (Expected: False -> {'PASS' if not acc.get('state_says_release_eligible') else 'FAIL'})")
        print(f"  Says all tests passed: {acc.get('state_says_all_tests_passed')} (Expected: False -> {'PASS' if not acc.get('state_says_all_tests_passed') else 'FAIL'})")

        # 9. Profit totals
        pnl = results.get("evidence_profit_totals", {})
        print(f"Probe 9 (Evidence Backtest Profit Totals): {pnl}")

        # Strict Automated Assertions
        failures = []
        for k in ["all_1344_records_equal", "raw_96_prices_equal", "processed_96_prices_equal", "raw_hash_matches_metadata"]:
            if not syn.get(k):
                failures.append(f"Probe 1 failure: {k} is not True")
        for k, v in qc.items():
            if v is not False:
                failures.append(f"Probe 2 failure: {k} was accepted ({v})")
        if rev_content != "first":
            failures.append(f"Probe 3 failure: original.csv content modified to '{rev_content}'")
        if short_soc != 0.50:
            failures.append(f"Probe 4 failure: short_soc is {short_soc}, expected 0.50")
        if half != 0:
            failures.append(f"Probe 5 failure: half_day_backtested_rows is {half}, expected 0")
        if mixed != 0:
            failures.append(f"Probe 5 failure: mixed_da_rt_result_rows is {mixed}, expected 0")
        if fp.get("production_parquet_exists") or fp.get("public_html_exists"):
            failures.append(f"Probe 6 failure: fixture pipeline leaked into production")
        if live_fail.get("exit") != 1 or live_fail.get("status", {}).get("status") != "failed":
            failures.append(f"Probe 7 failure: live failure did not record status=failed with exit=1")
        if acc.get("state_says_release_eligible") or acc.get("state_says_all_tests_passed"):
            failures.append(f"Probe 8 failure: acceptance falsely claimed release eligible")

        if failures:
            print("\nPROBE SUITE FAILED with errors:")
            for f in failures:
                print(f"  - {f}")
            sys.exit(1)
        else:
            print("\nALL ORIGINAL PROBE ASSERTIONS PASSED 100% (EXIT CODE: 0)")
            sys.exit(0)
