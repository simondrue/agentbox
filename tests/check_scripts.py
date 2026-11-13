#!/usr/bin/env python3
"""Check installation and launcher behavior without Docker or touching real state."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    repo = Path(__file__).resolve().parents[1]
    for script in ("agentbox", "install.sh"):
        subprocess.run(["bash", "-n", str(repo / script)], check=True)

    with tempfile.TemporaryDirectory(prefix="agentbox-check-") as temporary:
        root = Path(temporary)
        home = root / "test home"
        project = home / "project space"
        source = root / "source tree"
        mocks = root / "mock-bin"
        log = root / "calls.jsonl"
        project.mkdir(parents=True)
        mocks.mkdir()
        for name in ("install.sh", "agentbox", "Dockerfile", "compose.yaml", ".dockerignore",
                     "proxy/Dockerfile", "proxy/squid.conf", "proxy/.dockerignore"):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, target)

        mock = f"#!{sys.executable}\n" + '''
import json, os, sys
from pathlib import Path
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["MOCK_LOG"], "a") as log:
    log.write(json.dumps([tool, args, os.environ.get("AGENTBOX_WORKSPACE")]) + "\\n")
if tool == "uname":
    print(os.environ.get("MOCK_OS", "Darwin"))
elif tool == "docker":
    if "info" in args and os.environ.get("MOCK_STOPPED"):
        sys.exit(1)
    if "version" in args and "--format" in args:
        print(os.environ.get("MOCK_ENGINE", "28.0.0"))
    if "build" in args and os.environ.get("MOCK_BUILD_FAIL"):
        sys.exit(1)
'''
        for name in ("uname", "docker", "colima"):
            command = mocks / name
            command.write_text(mock)
            command.chmod(0o755)

        # Isolate each child process's home; never read the developer's Codex files.
        env = dict(os.environ, HOME=str(home), MOCK_LOG=str(log),
                   PATH=str(mocks) + os.pathsep + os.environ["PATH"])

        def run(script, *args, cwd=project, success=True, **overrides):
            result = subprocess.run(
                ["bash", str(script), *args], cwd=cwd,
                env=dict(env, **overrides), text=True, capture_output=True, timeout=15,
            )
            assert (result.returncode == 0) == success, result.stdout + result.stderr
            return result.stdout + result.stderr

        def calls():
            return [json.loads(line) for line in log.read_text().splitlines()]

        installer = source / "install.sh"
        config = home / ".config/agentbox"
        launcher = home / ".local/bin/agentbox"
        assert "Usage" in run(installer, "--unknown", success=False)
        assert "macOS" in run(installer, MOCK_OS="Linux", success=False)
        assert "AGENTS.md" in run(installer, success=False)
        (home / ".codex/skills").mkdir(parents=True)
        instructions = home / ".codex/AGENTS.md"
        instructions.symlink_to(source / "Dockerfile")
        assert "AGENTS.md" in run(installer, success=False)
        instructions.unlink()
        instructions.write_text("Test instructions\n")
        assert "28+" in run(installer, MOCK_ENGINE="27.5.1", success=False)
        assert not config.exists()

        run(installer, MOCK_STOPPED="1")
        assert ["colima", ["start"], None] in calls()
        for name in ("Dockerfile", "compose.yaml", ".dockerignore", "proxy/Dockerfile",
                     "proxy/squid.conf", "proxy/.dockerignore"):
            assert (config / name).read_bytes() == (source / name).read_bytes()
        assert launcher.read_bytes() == (source / "agentbox").read_bytes()
        assert os.access(launcher, os.X_OK)
        assert calls()[-1] == ["docker", ["--context", "colima", "compose", "-f",
                                        str(config / "compose.yaml"), "build", "agent", "proxy"],
                               str(source)]

        (config / "Dockerfile").write_text("Local customization\n")
        assert "--force" in run(installer, success=False)
        assert (config / "Dockerfile").read_text() == "Local customization\n"
        run(installer, "--force")
        assert (config / "Dockerfile").read_bytes() == (source / "Dockerfile").read_bytes()
        assert "Test instructions" in instructions.read_text()
        run(installer, "--force", MOCK_BUILD_FAIL="1", success=False)

        (config / "proxy/squid.conf").unlink()
        (config / "proxy/squid.conf").symlink_to(instructions)
        assert "symlink destination" in run(installer, "--force", success=False)
        assert "Test instructions" in instructions.read_text()
        (config / "proxy/squid.conf").unlink()
        run(installer, "--force")

        run(launcher, "--model", "example model", MOCK_STOPPED="1")
        assert calls()[-2][1][-4:] == ["up", "-d", "--wait", "proxy"]
        assert calls()[-1] == ["docker", ["--context", "colima", "compose", "-f",
            str(config / "compose.yaml"), "run", "--rm", "--no-deps", "agent", "codex",
            "--sandbox", "danger-full-access", "--ask-for-approval", "on-request",
            "--model", "example model"], str(project)]
        assert "specific project" in run(launcher, cwd=home, success=False)
        assert "specific project" in run(launcher, cwd=Path("/"), success=False)
        assert "outside" in run(launcher, cwd=config, success=False)
        (home / ".codex/skills").rmdir()
        (home / ".codex/skills").symlink_to(source, target_is_directory=True)
        assert "skills" in run(launcher, success=False)

    print("PASS: shell syntax; installer checks/copy/build/overwrite protection; launcher guards and arguments")


if __name__ == "__main__":
    main()
