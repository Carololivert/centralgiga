"""Executa os scripts de scripts_originais/ como subprocesso, transmitindo
o stdout linha a linha para o log (log ao vivo), sem reescrever a lógica."""
import io
import os
import subprocess
import sys


class LogWriter(io.TextIOBase):
    """Redireciona o stdout de uma função chamada in-process para log() (linha a linha).
    Use com contextlib.redirect_stdout(LogWriter(log))."""

    def __init__(self, log):
        self._log = log
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._log(line, "info")
        return len(s)

    def flush(self) -> None:
        if self._buf.strip():
            self._log(self._buf, "info")
        self._buf = ""

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts_originais",
)


def run_script_stream(script_name: str, log, args: list[str] | None = None, timeout: int = 180) -> str:
    """Roda scripts_originais/<script_name>, faz log() de cada linha do stdout
    e retorna o texto completo. Lança RuntimeError se o script falhar."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        raise RuntimeError(f"Script não encontrado: {script_path}")

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }
    cmd = [sys.executable, "-X", "utf8", script_path, *(args or [])]

    # stderr juntado ao stdout: evita deadlock de buffer e mantém ordem dos eventos.
    proc = subprocess.Popen(
        cmd,
        cwd=SCRIPTS_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    linhas: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if line.strip():
            linhas.append(line)
            log(line, "info")

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timeout: {script_name} passou de {timeout}s.")

    if proc.returncode != 0:
        cauda = "\n".join(linhas[-20:])
        raise RuntimeError(cauda or f"{script_name} terminou com código {proc.returncode}.")

    return "\n".join(linhas)
