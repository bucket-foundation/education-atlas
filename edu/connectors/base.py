"""Uniform Connector interface every education-atlas source implements.

Lifecycle: ``fetch()`` (paginated, polite, cached) -> ``normalize()`` (raw ->
canonical :class:`~edu.schema.Row` observations) -> ``emit()`` (merge into
``data/processed/<table>.parquet`` by stable ``obs_id``, dedup, keep newest).

Design goals
------------
- **Idempotent + resumable.** ``fetch()`` caches every raw response under
  ``data/raw/<source>/`` keyed by a stable page key; re-running skips pages
  already on disk. ``emit()`` merges on the table's primary key so re-emitting
  converges instead of duplicating.
- **Polite.** A shared :class:`HttpClient` honors ``Retry-After``, backs off on
  429/503, sends a descriptive User-Agent, sleeps a configurable delay.
- **Schema-true.** Every row passes through :func:`edu.schema.coerce`, so an
  emitted parquet always has the canonical column set in canonical order.
- **Provenance always.** Connectors stamp ``source`` / ``source_url`` / ``as_of``
  on every row. A row without provenance is a bug the validator catches.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

import requests

from edu import schema
from edu.schema import Row

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"

DEFAULT_UA = (
    "education-atlas/0.1 (+https://github.com/bucket-foundation/education-atlas; "
    "mailto:gianyrox@gmail.com)"
)

# Primary key per table -- the dedup subset for emit().
PRIMARY_KEY = {
    "observation": ["obs_id"],
    "country": ["country_code"],
    "indicator": ["indicator_code"],
    "problem": ["problem_id"],
}


class HttpClient:
    """Polite HTTP client: retries, ``Retry-After`` honoring, backoff."""

    def __init__(self, user_agent: str = DEFAULT_UA, delay: float = 0.15,
                 max_retries: int = 5, max_retry_after: float = 120.0):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.delay = delay
        self.max_retries = max_retries
        self.max_retry_after = max_retry_after

    def get(self, url: str, params: dict | None = None, timeout: float = 45):
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
            except requests.RequestException as exc:
                wait = self.delay * (2 ** attempt)
                print(f"  net retry ({exc}); sleeping {wait:.1f}s")
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                if self.delay:
                    time.sleep(self.delay)
                return resp

            if resp.status_code in (429, 503):
                ra = resp.headers.get("Retry-After")
                try:
                    wait = min(float(ra), self.max_retry_after) if ra else \
                        self.delay * (2 ** attempt)
                except ValueError:
                    wait = self.delay * (2 ** attempt)
                print(f"  HTTP {resp.status_code}; backoff {wait:.1f}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
                continue

            print(f"  HTTP {resp.status_code}: {resp.text[:160]}")
            return None
        return None


class Connector(ABC):
    """Base class. A source implements ``source``, ``fetch`` and ``normalize``."""

    source: str = "base"
    user_agent: str = DEFAULT_UA
    delay: float = 0.15

    def __init__(self, raw_dir: Path | None = None,
                 processed_dir: Path | None = None):
        self.raw_dir = (raw_dir or DATA_RAW) / self.source
        self.processed_dir = processed_dir or DATA_PROCESSED
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.http = HttpClient(user_agent=self.user_agent, delay=self.delay)

    # ----- raw cache (idempotent / resumable) ----------------------------- #

    def _raw_path(self, page_key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in page_key)
        return self.raw_dir / f"{safe}.json"

    def cache_raw(self, page_key: str, payload) -> Path:
        path = self._raw_path(page_key)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def load_raw(self, page_key: str):
        path = self._raw_path(page_key)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def has_raw(self, page_key: str) -> bool:
        return self._raw_path(page_key).exists()

    def iter_cached_raw(self) -> Iterator[dict]:
        for path in sorted(self.raw_dir.glob("*.json")):
            yield json.loads(path.read_text(encoding="utf-8"))

    # ----- the interface a source implements ------------------------------ #

    @abstractmethod
    def fetch(self, **kwargs) -> Iterable[dict]:
        """Yield raw pages, caching each under ``data/raw``. Resumable."""

    @abstractmethod
    def normalize(self, raw_pages: Iterable[dict]) -> Iterator[Row]:
        """Turn raw pages into canonical :class:`Row` objects."""

    # ----- emit (merge into parquet by primary key) ----------------------- #

    def emit(self, rows: Iterable[Row]) -> dict[str, int]:
        """Merge rows into ``data/processed/<table>.parquet`` by primary key.

        Newest ``as_of`` wins per key. Returns per-table count after merge.
        """
        import pandas as pd

        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row.table].append(schema.coerce(row.table, row.data))

        counts: dict[str, int] = {}
        for table, new_rows in grouped.items():
            if not new_rows:
                continue
            new_df = pd.DataFrame(new_rows)
            path = self.processed_dir / f"{table}.parquet"
            if path.exists():
                old_df = pd.read_parquet(path)
                combined = pd.concat([old_df, new_df], ignore_index=True)
            else:
                combined = new_df

            key = PRIMARY_KEY[table]
            sort_col = "as_of" if "as_of" in combined.columns else key[0]
            combined = combined.sort_values(sort_col).drop_duplicates(
                subset=key, keep="last")
            combined = combined.reindex(columns=schema.ENTITY_TABLES[table])
            combined.to_parquet(path, index=False)
            counts[table] = len(combined)

        return counts

    def run(self, **fetch_kwargs) -> dict[str, int]:
        pages = list(self.fetch(**fetch_kwargs))
        rows = self.normalize(pages)
        return self.emit(rows)
