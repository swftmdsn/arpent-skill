import json
import os
import queue
import re
import shlex
import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath

from . import PROTOCOL_VERSION
from .errors import AdapterError, ValidationError
from .jsonio import canonical_json, parse_json
from .schema import validate_adapter_response


class ReplayAdapter:
    name = "replay"

    def __init__(self, traces):
        self.traces = traces

    def evaluate(self, scenario):
        return self.traces[scenario["id"]]

    def close(self):
        return None


class StatefulCliAdapter:
    """Execute declared CLI events; replay non-command events without modeling an agent."""

    name = "stateful-cli"

    def __init__(self, traces, repository_root, timeout_seconds=30.0):
        self.traces = traces
        self.repository_root = Path(repository_root).resolve()
        self.timeout_seconds = timeout_seconds
        self.sandboxes = []
        self.last_vault_root = None

    def evaluate(self, scenario):
        sandbox = tempfile.TemporaryDirectory(prefix="arpent-stateful-")
        self.sandboxes.append(sandbox)
        root = Path(sandbox.name)
        home = root / "home"
        home.mkdir()
        vault = root / "vault"
        self.last_vault_root = vault
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        python_path = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(self.repository_root), python_path) if part
        )
        mode = scenario["fixture"]["vault_mode"]
        if mode != "none":
            arguments = [sys.executable, "-m", "scripts.cli", "init", str(vault)]
            if mode == "minimal":
                arguments.append("--minimal")
            initialized = subprocess.run(
                arguments,
                cwd=str(self.repository_root),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            if initialized.returncode != 0:
                raise AdapterError("stateful vault init failed: %s" % (initialized.stderr or initialized.stdout))
            environment["ARPENT_VAULT_ROOT"] = str(vault)
        else:
            vault.mkdir()
            environment.pop("ARPENT_VAULT_ROOT", None)
        for document in scenario["fixture"]["documents"]:
            destination = vault / document["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8", newline="") as handle:
                handle.write(document["content"])
        if mode != "none" and scenario["fixture"]["confirmation"] in (
            "always", "explicit-intent", "never",
        ):
            operations_path = vault / "06_indexes" / "cli" / "operations.yaml"
            operations = operations_path.read_text(encoding="utf-8")
            operations = re.sub(
                r"(?m)^(  policy: ).+$",
                r"\g<1>" + scenario["fixture"]["confirmation"],
                operations,
                count=1,
            )
            with operations_path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(operations)

        events = []
        latest_plan_hash = None
        for declared in self.traces[scenario["id"]]["events"]:
            if declared["type"] == "command":
                command = declared["command"]
                if latest_plan_hash is not None and "--plan-hash" in command:
                    command = re.sub(
                        r"(--plan-hash\s+)[a-f0-9]{64}(?=\s|$)",
                        r"\g<1>" + latest_plan_hash,
                        command,
                        count=1,
                    )
                executed = self._execute(command, environment, home, root)
                events.append(executed)
                if executed["exit_code"] == 0:
                    try:
                        output = json.loads(executed["output"])
                    except (json.JSONDecodeError, UnicodeError):
                        output = None
                    if isinstance(output, dict) and re.fullmatch(
                        r"[a-f0-9]{64}", str(output.get("plan_sha256", "")),
                    ):
                        latest_plan_hash = output["plan_sha256"]
            elif declared["type"] == "write":
                destination = vault / declared["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("w", encoding="utf-8", newline="") as handle:
                    handle.write(declared["content"])
                events.append({
                    "type": "write",
                    "path": declared["path"],
                    "content": destination.read_text(encoding="utf-8"),
                })
            else:
                events.append(dict(declared))
        return {
            "schema_version": self.traces[scenario["id"]]["schema_version"],
            "scenario_id": scenario["id"],
            "provider_usage": None,
            "events": events,
        }

    @staticmethod
    def _json_field(value, dotted_path):
        current = value
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise KeyError(dotted_path)
            current = current[part]
        return current

    @staticmethod
    def _json_contains(actual, expected):
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(
                key in actual and StatefulCliAdapter._json_contains(actual[key], item)
                for key, item in expected.items()
            )
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(
                StatefulCliAdapter._json_contains(left, right)
                for left, right in zip(actual, expected)
            )
        return actual == expected

    def observe_postconditions(self, golden, trace):
        checks = []
        commands = [event for event in trace["events"] if event["type"] == "command"]
        for postcondition in golden.get("postconditions", []):
            kind = postcondition["kind"]
            pattern = postcondition.get("command", postcondition.get("path"))
            passed = False
            detail = "no matching command event"
            if kind == "path_exists":
                relative_path = postcondition["path"]
                passed = (self.last_vault_root / relative_path).is_file()
                detail = "%s %s" % (relative_path, "exists" if passed else "is missing")
            else:
                matching = [event for event in commands if re.search(postcondition["command"], event["command"])]
                for event in matching:
                    try:
                        output = json.loads(event["output"])
                    except (json.JSONDecodeError, UnicodeError) as exc:
                        detail = "command output is not JSON: %s" % exc
                        continue
                    if kind == "command_json_fields":
                        passed = self._json_contains(output, postcondition["fields"])
                        detail = "observed JSON fields matched" if passed else "observed JSON fields differ"
                    else:
                        try:
                            relative_path = self._json_field(output, postcondition["field"])
                        except KeyError:
                            detail = "JSON field %s is missing" % postcondition["field"]
                            continue
                        path = PurePosixPath(relative_path) if isinstance(relative_path, str) else None
                        safe = path is not None and not path.is_absolute() and ".." not in path.parts
                        passed = safe and (self.last_vault_root / relative_path).is_file()
                        detail = "%s %s" % (
                            relative_path,
                            "exists in the vault" if passed else "is not a safe existing vault file",
                        )
                    if passed:
                        break
            checks.append({
                "kind": "postcondition_%s" % kind,
                "pattern": pattern,
                "passed": passed,
                "hard": not passed,
                "detail": detail,
            })
        return checks

    def _execute(self, command, environment, home, root):
        arguments = shlex.split(command)
        if not arguments or arguments[0] not in ("arpent", "arp"):
            return {"type": "command", "command": command, "output": "unsupported command", "exit_code": 127}
        expanded = []
        for argument in arguments[1:]:
            if argument == "~":
                argument = str(home)
            elif argument.startswith("~/"):
                argument = str(home / argument[2:])
            elif argument.startswith("/tmp/arpent-benchmark/"):
                argument = str(root / "tmp" / argument[len("/tmp/arpent-benchmark/"):])
            expanded.append(argument)
        completed = subprocess.run(
            [sys.executable, "-m", "scripts.cli", *expanded],
            cwd=str(self.repository_root),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        output = completed.stdout.rstrip("\r\n")
        if not output:
            output = completed.stderr.rstrip("\r\n")
        return {
            "type": "command",
            "command": command,
            "output": output,
            "exit_code": completed.returncode,
        }

    def close(self):
        while self.sandboxes:
            self.sandboxes.pop().cleanup()


class CommandJsonlAdapter:
    name = "command-jsonl"

    def __init__(self, command, timeout_seconds=120.0):
        arguments = shlex.split(command)
        if not arguments:
            raise AdapterError("adapter command is empty")
        self.timeout_seconds = timeout_seconds
        try:
            self.process = subprocess.Popen(
                arguments,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise AdapterError("cannot start adapter: %s" % exc) from exc
        self.responses = queue.Queue()
        self.stderr_lines = []
        self.stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _read_stdout(self):
        try:
            for line in self.process.stdout:
                self.responses.put(("line", line))
        finally:
            self.responses.put(("eof", None))

    def _read_stderr(self):
        for line in self.process.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def evaluate(self, scenario):
        request = {
            "protocol_version": PROTOCOL_VERSION,
            "type": "evaluate",
            "scenario": scenario,
        }
        try:
            self.process.stdin.write(canonical_json(request) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AdapterError("adapter closed its input: %s" % self._stderr()) from exc
        try:
            kind, payload = self.responses.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise AdapterError("adapter timed out after %.1fs" % self.timeout_seconds) from exc
        if kind == "eof":
            raise AdapterError("adapter exited before responding: %s" % self._stderr())
        if not payload.strip():
            raise AdapterError("adapter emitted a blank JSONL response")
        try:
            response = parse_json(payload, "adapter stdout")
            return validate_adapter_response(response, scenario)
        except ValidationError as exc:
            raise AdapterError(str(exc)) from exc

    def _stderr(self):
        text = "\n".join(self.stderr_lines)
        return text[-4000:] if text else "no stderr"

    def close(self):
        shutdown_error = None
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                return_code = self.process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                shutdown_error = AdapterError("adapter did not exit after stdin closed")
                return_code = self.process.returncode
        else:
            return_code = self.process.returncode
            if not self.process.stdin.closed:
                self.process.stdin.close()
        self.stdout_thread.join(timeout=1)
        self.stderr_thread.join(timeout=1)
        self.process.stdout.close()
        self.process.stderr.close()
        extra_responses = []
        while True:
            try:
                kind, payload = self.responses.get_nowait()
            except queue.Empty:
                break
            if kind == "line" and payload.strip():
                extra_responses.append(payload)
        if shutdown_error is not None:
            raise shutdown_error
        if return_code != 0:
            raise AdapterError("adapter exited with %d: %s" % (return_code, self._stderr()))
        if extra_responses:
            raise AdapterError("adapter emitted %d unsolicited response line(s)" % len(extra_responses))
