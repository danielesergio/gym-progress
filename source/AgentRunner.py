import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from source.Config import Config


class AgentRunner:
    def __init__(self, config: Config):
        self._config = config

    def run(self, agent_type: Optional[str], prompt: str, timeout: int = 720) -> str:
        """Invoca claude CLI in modalita' non-interattiva. Il prompt viene passato via stdin
        per evitare il limite Windows sulla lunghezza degli argomenti (WinError 206)."""
        cmd = [
            "claude", "--print",
            "--dangerously-skip-permissions",
            "--output-format", "text",
        ]
        if agent_type:
            cmd += ["--agent", agent_type]

        print(f"[ACTION] LLM: {agent_type or 'default'}", flush=True)
        try:
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=self._config.PROJECT_ROOT, timeout=timeout,
            )
            if result.returncode != 0:
                print(f"[ERROR ] Agente {agent_type} rc={result.returncode}: {result.stderr[:300]}", flush=True)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"[ERROR ] Timeout ({timeout}s) per agente {agent_type}", flush=True)
            return ""

    def run_parallel(self, tasks: list, timeout: int = 720) -> dict:
        """Lancia piu' agenti in parallelo. tasks = [(agent_type, prompt), ...]"""
        results: dict = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(self.run, ag, pr, timeout): ag for ag, pr in tasks}
            for future in as_completed(futures):
                ag = futures[future]
                try:
                    results[ag or "default"] = future.result()
                except Exception as e:
                    print(f"[ERROR ] Agente {ag} eccezione: {e}", flush=True)
                    results[ag or "default"] = ""
        return results
