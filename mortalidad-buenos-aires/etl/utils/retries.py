"""Decorador de reintentos con backoff exponencial para llamadas externas."""
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

http_retry = retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (httpx.HTTPError, httpx.TimeoutException, ConnectionError)
    ),
)
