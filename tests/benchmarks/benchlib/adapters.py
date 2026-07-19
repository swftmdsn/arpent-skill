import queue
import shlex
import subprocess
import threading

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
