"""Cliente HTTP com retry e pausa entre chamadas."""
from __future__ import annotations

import time

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

UA = "financas-sl/0.1 (pesquisa com dados publicos)"


def _transitorio(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class Cliente:
    def __init__(self, pausa: float = 0.25, timeout: float = 60):
        self.pausa = pausa
        self.http = httpx.Client(timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True)

    @retry(retry=retry_if_exception(_transitorio), stop=stop_after_attempt(5),
           wait=wait_exponential(multiplier=2, max=60), reraise=True)
    def get_json(self, url: str, params: dict | None = None):
        time.sleep(self.pausa)
        r = self.http.get(url, params=params)
        if r.status_code == 204:
            return None  # "sem dados" de verdade (o PNCP responde assim para mês ou contrato sem nada)
        # o status vem antes do corpo vazio: um 404 ou 500 sem corpo é erro, não "sem dados"
        r.raise_for_status()
        if not r.content:
            return None
        return r.json()

    @retry(retry=retry_if_exception(_transitorio), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, max=20), reraise=True)
    def get_bytes(self, url: str) -> bytes:
        """Arquivo binário, como uma foto. Erro HTTP sobe como exceção."""
        time.sleep(self.pausa)
        r = self.http.get(url)
        r.raise_for_status()
        return r.content

    def fechar(self):
        self.http.close()
