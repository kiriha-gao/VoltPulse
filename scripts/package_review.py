import os
import re
import sys
import zipfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent


def scan_secrets(file_path: Path) -> list:
    """Scans a file for potential passwords, tokens, private keys."""
    # Skip self from scanning
    if file_path.name == "package_review.py":
        return []

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    findings = []
    # Check for private keys
    pk_header = "BEGIN " + "PRIVATE KEY"
    if pk_header in text:
        findings.append("Private key block detected")
    # Check for github tokens
    if re.search(r"ghp_[A-Za-z0-9_]{30,}", text):
        findings.append("GitHub token detected")
    # Check for hardcoded credentials pattern
    matches = re.findall(r"(?i)(api[_-]?key|password|secret|access_token)\s*[:=]\s*['\"]([^'\"]+)['\"]", text)
    for k, v in matches:
        if len(v) > 10 and not v.startswith("${") and not v.startswith("YOUR_") and "example" not in v.lower():
            findings.append(f"Possible secret for {k}")

    return findings


def build_review_zip():
    zip_path = project_root / "VoltPulse_REVIEW.zip"
    if zip_path.exists():
        zip_path.unlink()

    included_dirs = [
        "config",
        "src",
        "scripts",
        "tests",
        ".github/workflows",
        "docs",
        "audit",
        "evidence",
        "public",
        "reports"
    ]

    included_files = [
        "pyproject.toml",
        "requirements.txt",
        "README.md",
        "PROJECT_STATE.md",
        "DECISIONS.md",
        "ACCEPTANCE.md",
        "RUNBOOK.md",
        "LICENSE",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "NOTES.md",
        ".gitattributes",
        ".gitignore",
        ".env.example"
    ]

    excluded_dir_names = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "logs",
        "data"  # Full historical raw archive excluded; evidence/ is included instead
    }

    files_to_zip = []
    secrets_found = []

    # 1. Add individual files
    for fname in included_files:
        fpath = project_root / fname
        if fpath.exists() and fpath.is_file():
            sec = scan_secrets(fpath)
            if sec:
                secrets_found.append((fpath, sec))
            files_to_zip.append(fpath)

    # 2. Add directories
    for dir_rel in included_dirs:
        dir_path = project_root / dir_rel
        if not dir_path.exists():
            continue
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in excluded_dir_names and not d.endswith(".egg-info")]
            for f in files:
                if f.endswith((".pyc", ".pyo", ".tmp", ".log")) and f != "AUDIT_RUN.log":
                    continue
                if f == ".env":
                    continue
                fp = Path(root) / f
                sec = scan_secrets(fp)
                if sec:
                    secrets_found.append((fp, sec))
                files_to_zip.append(fp)

    print(f"Total candidate files to package: {len(files_to_zip)}")
    if secrets_found:
        print(f"WARNING: Sensitive information detected in {len(secrets_found)} files:")
        for fp, issues in secrets_found:
            print(f" - {fp}: {issues}")
        sys.exit(1)
    else:
        print("Security scan PASSED: Zero sensitive credentials detected.")

    # Write ZIP
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in files_to_zip:
            rel_path = fp.relative_to(project_root)
            zf.write(fp, arcname=str(rel_path))

    zip_size_bytes = zip_path.stat().st_size
    zip_size_kb = zip_size_bytes / 1024
    print(f"VoltPulse_REVIEW.zip created successfully at: {zip_path}")
    print(f"Archive Size: {zip_size_kb:.2f} KB ({zip_size_bytes} bytes)")

    # Print top-level tree inside zip
    top_level_items = set()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            parts = Path(name).parts
            if len(parts) > 1:
                top_level_items.add(parts[0] + "/")
            else:
                top_level_items.add(parts[0])

    print("\nTop-level archive structure:")
    for item in sorted(top_level_items):
        print(f"  {item}")

    return zip_path, zip_size_bytes, sorted(top_level_items)


if __name__ == "__main__":
    build_review_zip()
