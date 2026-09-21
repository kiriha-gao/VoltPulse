import time
from typing import Optional, Dict, Any
import requests

from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.ingestion.downloader")


class RobustDownloader:
    """
    HTTP downloader with exponential backoff retry adhering to
    VoltPulse Specification Section 32.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0, timeout: int = 15):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VoltPulse/1.0 (Open-source Energy Research Platform; Automated Tracker)"
        })

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        """
        Executes an HTTP GET with exponential backoff (retries up to 3 times).
        """
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Downloading from {url} (Attempt {attempt}/{self.max_retries})")
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except (requests.RequestException, Exception) as e:
                last_exception = e
                wait_time = self.base_delay * (2 ** (attempt - 1))
                logger.warning(f"Request failed: {e}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)

        logger.error(f"All {self.max_retries} attempts failed for URL: {url}")
        raise RuntimeError(f"Downloader failed after {self.max_retries} attempts: {last_exception}") from last_exception
