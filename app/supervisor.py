from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    port = os.getenv("PORT", "8000")
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.sse_app:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
        [
            sys.executable,
            "-m",
            "app.workers.research_worker",
        ],
    ]
    processes: list[subprocess.Popen] = []

    shutting_down = False

    def shutdown(signum=None, frame=None) -> None:
        nonlocal shutting_down
        if not shutting_down:
            shutting_down = True
            for process in processes:
                if process.poll() is None:
                    process.terminate()
        deadline = time.monotonic() + 15
        for process in processes:
            if process.poll() is None:
                remaining = max(0, deadline - time.monotonic())
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        for command in commands:
            processes.append(subprocess.Popen(command))
        while True:
            for process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(
                        f"Child process {process.args} exited "
                        f"with code {exit_code}; stopping service.",
                        flush=True,
                    )
                    shutdown()
                    return exit_code or 1
            time.sleep(1)
    except Exception:
        shutdown()
        raise
    finally:
        shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
