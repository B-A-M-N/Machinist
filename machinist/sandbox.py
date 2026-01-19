from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence


class SandboxError(RuntimeError):
    pass


@dataclass
class SandboxPolicy:
    allow_net: bool = False
    readonly_paths: Sequence[Path] = field(default_factory=list)
    writable_paths: Sequence[Path] = field(default_factory=list)
    extra_args: Sequence[str] = field(default_factory=list)
    memory_limit_mb: int = 1024  # Default 1GB
    cpu_time_limit_sec: int = 60 # Default 60s


class BwrapSandbox:
    """
    Bubblewrap-based sandbox runner.
    - read-only binds for system dirs
    - writable scratch dir mounted at /scratch
    - network disabled by default
    """

    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        self.policy = policy or SandboxPolicy()
        self._ensure_bwrap()

    def _ensure_bwrap(self) -> None:
        if shutil.which("bwrap") is None:
            raise SandboxError("bwrap not found on PATH; install bubblewrap or adjust sandbox runner.")

    def _base_args(self, scratch: Path, workdir: Path) -> List[str]:
        args = [
            "--unshare-all",
            "--die-with-parent",
            "--dev", "/dev",
            "--proc", "/proc",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--bind", str(workdir), str(workdir),
            "--bind", str(scratch), "/scratch",
            "--chdir", str(workdir),
            "--tmpfs", "/tmp",
            "--tmpfs", "/var/tmp",
        ]
        if not self.policy.allow_net:
            args.append("--unshare-net")
        for path in self.policy.readonly_paths:
            args.extend(["--ro-bind", str(path), str(path)])
        for path in self.policy.writable_paths:
            args.extend(["--bind", str(path), str(path)])
        args.extend(self.policy.extra_args)
        return args

    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        workdir: Path | str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        on_output: callable | None = None,
        name: str | None = None,
    ) -> subprocess.CompletedProcess:
        workdir_path = Path(workdir or ".").resolve()
        # Ensure workdir exists; if not, create it (sandbox should not fail on missing artifacts dir).
        workdir_path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="machinist-scratch-") as scratch_dir:
            scratch_path = Path(scratch_dir)
            
            # Prepare resource limits command prefix
            cmd_prefix = []
            if shutil.which("prlimit"):
                if self.policy.memory_limit_mb > 0:
                     mem_bytes = self.policy.memory_limit_mb * 1024 * 1024
                     cmd_prefix.extend(["prlimit", f"--as={mem_bytes}"])
                if self.policy.cpu_time_limit_sec > 0:
                     cmd_prefix.extend(["prlimit", f"--cpu={self.policy.cpu_time_limit_sec}"])

            bwrap_cmd = ["bwrap", *self._base_args(scratch_path, workdir_path), "--", *cmd_prefix, *command]
            
            if not stream:
                result = subprocess.run(
                    bwrap_cmd,
                    cwd=str(workdir_path),
                    env=os.environ | (env or {}),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return result

            # Streaming mode: read stdout/stderr but with a timeout.
            proc = subprocess.Popen(
                bwrap_cmd,
                cwd=str(workdir_path),
                env=os.environ | (env or {}),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                # Use communicate to read all output with a timeout. This is safer than
                # iterating over pipes directly, which can block indefinitely.
                stdout, stderr = proc.communicate(timeout=timeout)
                if on_output:
                    # Output is buffered, so we send it all at once after completion.
                    if stdout:
                        on_output(name or "", stdout)
                    if stderr:
                        on_output(name or "", stderr)

                return subprocess.CompletedProcess(
                    args=bwrap_cmd,
                    returncode=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            except subprocess.TimeoutExpired as e:
                proc.kill()
                # After timeout, call communicate again to get any final output.
                remaining_stdout, remaining_stderr = proc.communicate()
                
                # Combine output from before and after timeout.
                final_stdout = (e.stdout or "") + (remaining_stdout or "")
                final_stderr = (e.stderr or "") + (remaining_stderr or "")

                if on_output:
                    if final_stdout:
                        on_output(name or "", final_stdout)
                    if final_stderr:
                        on_output(name or "", final_stderr)

                return subprocess.CompletedProcess(
                    args=bwrap_cmd,
                    returncode=-1,  # Using -1 to indicate timeout
                    stdout=final_stdout,
                    stderr=final_stderr,
                )
