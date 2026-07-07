"""Executa os scripts de scripts_originais/ — como subprocesso (transmitindo o
stdout linha a linha p/ log ao vivo) ou carregados in-process via importlib.

O código novo é organizado em pastas (comum/, vendas/, relatorios/, telefonia/,
conferencia-os/) e usa módulos compartilhados de comum/ (sgp_api, focus_api…),
que cada script coloca no sys.path sozinho. Por isso carregamos os scripts por
CAMINHO (importlib.util), sem depender de nome de pacote — assim lidamos com a
pasta hifenizada `conferencia-os` e com os imports de comum/ sem atrito."""
import importlib.util
import io
import os
import re
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


def _caminho_script(caminho_rel: str) -> str:
    """Resolve 'relatorios/main.py' contra SCRIPTS_DIR (aceita / em qualquer SO)."""
    return os.path.join(SCRIPTS_DIR, *caminho_rel.split("/"))


def carregar_script(caminho_rel: str):
    """Importa scripts_originais/<caminho_rel> como módulo isolado (importlib),
    sem depender de nome de pacote. Cada script coloca comum/ no sys.path por conta
    própria (sys.path.insert no topo do arquivo), então os `from sgp_api import …`
    resolvem. Recarrega a cada chamada (pega a data/estado atuais)."""
    caminho = _caminho_script(caminho_rel)
    if not os.path.exists(caminho):
        raise RuntimeError(f"Script não encontrado: {caminho}")
    nome = "auto_" + re.sub(r"\W+", "_", caminho_rel)
    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não consegui carregar o script: {caminho}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod  # necessário p/ scripts que se auto-referenciam
    spec.loader.exec_module(mod)
    # cada script faz sys.path.insert(comum) no topo; num worker de vida longa isso
    # acumula duplicatas a cada job. Deduplica preservando a ordem (a 1ª ocorrência).
    vistos: set[str] = set()
    sys.path[:] = [p for p in sys.path if not (p in vistos or vistos.add(p))]
    return mod


def run_script_stream(caminho_rel: str, log, args: list[str] | None = None, timeout: int = 180) -> str:
    """Roda scripts_originais/<caminho_rel> como subprocesso, faz log() de cada
    linha do stdout e retorna o texto completo. Lança RuntimeError se falhar.

    `caminho_rel` pode ter subpasta, ex: 'relatorios/main.py'."""
    script_path = _caminho_script(caminho_rel)
    if not os.path.exists(script_path):
        raise RuntimeError(f"Script não encontrado: {script_path}")

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }
    cmd = [sys.executable, "-X", "utf8", script_path, *(args or [])]

    # cwd = SCRIPTS_DIR: o load_dotenv() dos scripts sobe a partir daqui e acha o
    # worker/.env; os módulos de comum/ são resolvidos por __file__ (não pelo cwd).
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
        linhas.append(line)          # preserva o relatório (inclui linhas em branco/separadores)
        if line.strip():
            log(line, "info")        # log ao vivo continua enxuto (sem linhas vazias)

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timeout: {caminho_rel} passou de {timeout}s.")

    if proc.returncode != 0:
        cauda = "\n".join(linhas[-20:])
        raise RuntimeError(cauda or f"{caminho_rel} terminou com código {proc.returncode}.")

    return "\n".join(linhas)
