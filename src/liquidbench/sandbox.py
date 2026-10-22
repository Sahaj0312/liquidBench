"""No host workspace mounts or arbitrary host command execution."""

import json
import subprocess
import uuid


class InfrastructureError(RuntimeError):
    pass


class ToolError(ValueError):
    pass


def docker(*args, input=None, timeout=30):
    try:
        proc = subprocess.run(
            ["docker", *args], input=input, text=True, capture_output=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InfrastructureError(f"Docker unavailable or timed out: {type(exc).__name__}") from exc
    if proc.returncode:
        raise InfrastructureError(f"Docker command failed: {proc.stderr[:1500]}")
    return proc.stdout.strip()


def image_id(tag):
    return docker("image", "inspect", "--format", "{{.Id}}", tag)


class Sandbox:
    def __init__(self, image, initial):
        self.image = image
        self.initial = initial
        self.name = "liquidbench-" + uuid.uuid4().hex

    def __enter__(self):
        try:
            docker(
                "run",
                "-d",
                "--name",
                self.name,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--user",
                "1000:1000",
                "--tmpfs",
                "/workspace:rw,nosuid,nodev,noexec,size=8m,mode=0777",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,noexec,size=16m",
                "--env",
                "HOME=/tmp",
                self.image,
            )
            self.call("_initialize", {"files": self.initial})
            return self
        except BaseException:
            self.close()
            raise

    def call(self, tool, args=None, timeout=25):
        output = docker(
            "exec",
            "-i",
            self.name,
            "python3",
            "/opt/liquidbench/tool.py",
            input=json.dumps({"tool": tool, "args": args or {}}),
            timeout=timeout,
        )
        try:
            reply = json.loads(output)
        except json.JSONDecodeError as exc:
            raise InfrastructureError("Container tool returned invalid JSON") from exc
        if "infrastructure_error" in reply:
            raise InfrastructureError(reply["infrastructure_error"])
        if not reply["ok"]:
            raise ToolError(reply["error"])
        return reply["result"]

    def snapshot(self):
        return self.call("_snapshot")

    def close(self):
        try:
            docker("rm", "-f", self.name, timeout=15)
        except InfrastructureError:
            # An already-removed container must not mask the original exception.
            pass

    def __exit__(self, *_):
        self.close()
