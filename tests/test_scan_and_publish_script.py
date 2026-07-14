from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "scan_and_publish.ps1"
REGISTER_SCRIPT = Path(__file__).parents[1] / "scripts" / "register_task.ps1"


def test_scheduled_scan_retries_git_and_recovers_pending_publish() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function Run-WithRetry" in source
    assert "function Configure-GitNetworkProxy" in source
    assert "GIT_CONFIG_COUNT" in source
    assert "Publish-PendingAutomationCommit" in source
    assert "Save-PendingAutomationCommit" in source
    assert "Test-AutomationGeneratedPath" in source
    assert "BRAVE_SEARCH_API_KEY" in source
    assert "search_healthcheck --provider brave --strict" in source


def test_scheduled_task_is_allowed_to_run_on_battery() -> None:
    source = REGISTER_SCRIPT.read_text(encoding="utf-8")

    assert "-AllowStartIfOnBatteries" in source
    assert "-DontStopIfGoingOnBatteries" in source


@pytest.mark.skipif(os.name != "nt", reason="The production automation is a Windows PowerShell script")
def test_status_refresh_queues_commit_until_git_remote_recovers(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    repo.mkdir()
    fake_bin.mkdir()
    (repo / "scripts").mkdir()
    (repo / "data").mkdir()
    shutil.copy2(SCRIPT, repo / "scripts" / SCRIPT.name)
    (repo / ".gitignore").write_text("logs/\nsite/\n", encoding="utf-8")
    (repo / "data" / "latest_candidates.json").write_text("{}\n", encoding="utf-8")
    (repo / "data" / "latest_sources.json").write_text("{}\n", encoding="utf-8")
    (repo / "data" / "latest_scan_manifest.json").write_text("{}\n", encoding="utf-8")
    (repo / "data" / "review_queue.json").write_text(
        '{"state":"old"}\n', encoding="utf-8"
    )
    (fake_bin / "python.cmd").write_text(
        "@echo off\r\n"
        "if not exist site mkdir site\r\n"
        "copy /y data\\latest_candidates.json site\\candidates.json >nul\r\n"
        "powershell -NoProfile -Command \"Set-Content -LiteralPath "
        "'data/review_queue.json' -Value '{\\\"state\\\":\\\"new\\\"}'\"\r\n"
        "exit /b 0\r\n",
        encoding="ascii",
    )

    _run(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.name", "Summa Test"], cwd=repo)
    _run(["git", "config", "user.email", "summa-test@example.invalid"], cwd=repo)
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "Initial snapshot"], cwd=repo)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=repo)
    _run(["git", "push", "-u", "origin", "main"], cwd=repo)
    initial_head = _run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    missing_remote = tmp_path / "missing.git"
    _run(["git", "remote", "set-url", "origin", str(missing_remote)], cwd=repo)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["SUMMA_GIT_RETRY_DELAY_SECONDS"] = "0"
    first = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo / "scripts" / SCRIPT.name),
            "-Mode",
            "Status",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    pending = repo / ".git" / "summa-pending-publish.json"
    assert first.returncode == 1
    assert pending.exists()
    assert _run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip() == initial_head
    assert _run(["git", "status", "--porcelain"], cwd=repo).stdout == ""

    _run(["git", "remote", "set-url", "origin", str(remote)], cwd=repo)
    second = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo / "scripts" / SCRIPT.name),
            "-Mode",
            "Status",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert second.returncode == 0, second.stderr
    assert not pending.exists()
    published = _run(
        ["git", f"--git-dir={remote}", "show", "main:data/review_queue.json"],
        cwd=tmp_path,
    ).stdout
    assert '"state":"new"' in published.replace(" ", "")


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
