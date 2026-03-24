"""
TradeOS India — Fyers master contract download and cache.

Downloads master contract CSVs from Fyers, parses them with Polars,
caches as parquet files, and provides search + option chain helpers.
Refreshes automatically if cache is older than 24 hours.
"""

from typing import Optional

import httpx
import polars as pl
from io import BytesIO

from storage.cache import (
    save_contracts,
    load_contracts,
    is_contracts_stale,
)
from utils.logger import get_logger

log = get_logger("brokers.fyers.contracts")

# ─── Master contract URLs ────────────────────────────────────────
MASTER_CONTRACT_URLS: dict[str, str] = {
    "NSE_CM": "https://public.fyers.in/sym_details/NSE_CM.csv",
    "NSE_FO": "https://public.fyers.in/sym_details/NSE_FO.csv",
    "BSE_CM": "https://public.fyers.in/sym_details/BSE_CM.csv",
    "MCX_COM": "https://public.fyers.in/sym_details/MCX_COM.csv",
    "CDS_FO": "https://public.fyers.in/sym_details/CDS_FO.csv",
}

# Expected CSV columns from Fyers master files
_EXPECTED_COLUMNS = [
    "Fytoken", "Symbol Details", "Exchange Instrument type",
    "Minimum lot size", "Tick size", "ISIN", "Trading Session",
    "Last update date", "Expiry date", "Symbol ticker",
    "Exchange", "Segment", "Scrip code", "Underlying scrip code",
    "Strike price", "Option type",
]


class FyersContracts:
    """Download, cache, and search Fyers master contracts.

    Usage:
        contracts = FyersContracts()
        await contracts.download_and_cache(["NSE_CM", "NSE_FO"])
        results = contracts.search("RELIANCE", "NSE_CM")
        chain = contracts.get_option_chain("NIFTY", "2024-08-29")
    """

    def __init__(self) -> None:
        self._dataframes: dict[str, pl.DataFrame] = {}

    # ═════════════════════════════════════════════════════════════
    # Download and cache
    # ═════════════════════════════════════════════════════════════

    async def download_and_cache(
        self,
        segments: Optional[list[str]] = None,
        force: bool = False,
    ) -> dict[str, int]:
        """Download master contract CSVs and cache as parquet.

        Args:
            segments: List of segment keys (e.g. ['NSE_CM', 'NSE_FO']).
                      If None, downloads all segments.
            force: If True, re-download even if cache is fresh.

        Returns:
            Dict of segment -> row count downloaded.
        """
        if segments is None:
            segments = list(MASTER_CONTRACT_URLS.keys())

        results: dict[str, int] = {}

        for segment in segments:
            url = MASTER_CONTRACT_URLS.get(segment)
            if not url:
                log.warning(f"Unknown segment: {segment}")
                continue

            # Skip if cache is fresh
            if not force and not is_contracts_stale(segment):
                cached = self._load_from_cache(segment)
                if cached is not None:
                    results[segment] = len(cached)
                    log.info(
                        f"{segment}: cache fresh ({len(cached)} contracts)"
                    )
                    continue

            try:
                df = await self._download_segment(segment, url)
                if df is not None and len(df) > 0:
                    save_contracts(segment, df)
                    self._dataframes[segment] = df
                    results[segment] = len(df)
                    log.info(
                        f"{segment}: downloaded {len(df)} contracts"
                    )
                else:
                    log.warning(f"{segment}: download returned empty data")
                    results[segment] = 0
            except Exception as exc:
                log.error(f"Failed to download {segment}: {exc}")
                # Try to use stale cache
                cached = self._load_from_cache(segment)
                if cached is not None:
                    results[segment] = len(cached)
                    log.info(f"{segment}: using stale cache ({len(cached)})")
                else:
                    results[segment] = 0

        return results

    async def _download_segment(
        self,
        segment: str,
        url: str,
    ) -> Optional[pl.DataFrame]:
        """Download a single segment CSV and parse it.

        Args:
            segment: Segment identifier.
            url: URL to download from.

        Returns:
            Polars DataFrame, or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            # Parse CSV with Polars
            df = pl.read_csv(
                BytesIO(resp.content),
                has_header=True,
                infer_schema_length=1000,
                ignore_errors=True,
            )

            log.debug(
                f"{segment}: parsed {len(df)} rows, "
                f"columns: {df.columns[:5]}..."
            )
            return df

        except httpx.HTTPStatusError as exc:
            log.error(f"HTTP error downloading {segment}: {exc}")
            return None
        except Exception as exc:
            log.error(f"Error parsing {segment} CSV: {exc}")
            return None

    def _load_from_cache(self, segment: str) -> Optional[pl.DataFrame]:
        """Load a segment from parquet cache into memory.

        Args:
            segment: Segment identifier.

        Returns:
            DataFrame if cache exists, else None.
        """
        if segment in self._dataframes:
            return self._dataframes[segment]

        df = load_contracts(segment)
        if df is not None:
            self._dataframes[segment] = df
        return df

    # ═════════════════════════════════════════════════════════════
    # Search
    # ═════════════════════════════════════════════════════════════

    def search(
        self,
        query: str,
        segment: str = "NSE_CM",
        max_results: int = 20,
    ) -> pl.DataFrame:
        """Fuzzy search contracts by symbol name.

        Args:
            query: Search string (e.g. 'RELIANCE', 'NIFTY').
            segment: Segment to search in.
            max_results: Maximum results to return.

        Returns:
            Filtered DataFrame of matching contracts.
        """
        df = self._load_from_cache(segment)
        if df is None:
            log.warning(f"No data for segment {segment}")
            return pl.DataFrame()

        query_upper = query.upper()

        # Search in Symbol ticker or Symbol Details columns
        ticker_col = "Symbol ticker" if "Symbol ticker" in df.columns else None
        details_col = (
            "Symbol Details" if "Symbol Details" in df.columns else None
        )

        if ticker_col:
            mask = df[ticker_col].cast(pl.Utf8).str.to_uppercase().str.contains(
                query_upper, literal=True
            )
            filtered = df.filter(mask)
        elif details_col:
            mask = df[details_col].cast(pl.Utf8).str.to_uppercase().str.contains(
                query_upper, literal=True
            )
            filtered = df.filter(mask)
        else:
            # Fallback: search first string column
            str_cols = [
                c for c in df.columns if df[c].dtype == pl.Utf8
            ]
            if not str_cols:
                return pl.DataFrame()
            mask = df[str_cols[0]].str.to_uppercase().str.contains(
                query_upper, literal=True
            )
            filtered = df.filter(mask)

        return filtered.head(max_results)

    # ═════════════════════════════════════════════════════════════
    # Option chain
    # ═════════════════════════════════════════════════════════════

    def get_option_chain(
        self,
        underlying: str,
        expiry: str,
        segment: str = "NSE_FO",
    ) -> pl.DataFrame:
        """Get the option chain (CE + PE) for an underlying and expiry.

        Args:
            underlying: Underlying symbol (e.g. 'NIFTY', 'BANKNIFTY').
            expiry: Expiry date string 'YYYY-MM-DD'.
            segment: Segment to search (default NSE_FO).

        Returns:
            DataFrame with CE and PE rows for the given underlying/expiry.
        """
        df = self._load_from_cache(segment)
        if df is None:
            log.warning(f"No data for segment {segment}")
            return pl.DataFrame()

        underlying_upper = underlying.upper()

        # Filter by underlying
        ticker_col = "Symbol ticker" if "Symbol ticker" in df.columns else None
        if ticker_col is None:
            log.warning("Symbol ticker column not found")
            return pl.DataFrame()

        mask_underlying = (
            df[ticker_col]
            .cast(pl.Utf8)
            .str.to_uppercase()
            .str.contains(underlying_upper, literal=True)
        )

        # Filter by expiry if column exists
        expiry_col = "Expiry date" if "Expiry date" in df.columns else None
        if expiry_col:
            mask_expiry = df[expiry_col].cast(pl.Utf8).str.contains(
                expiry, literal=True
            )
            filtered = df.filter(mask_underlying & mask_expiry)
        else:
            filtered = df.filter(mask_underlying)

        # Filter for option types CE and PE
        option_col = "Option type" if "Option type" in df.columns else None
        if option_col:
            mask_options = df[option_col].cast(pl.Utf8).is_in(["CE", "PE"])
            filtered = filtered.filter(
                filtered[option_col].cast(pl.Utf8).is_in(["CE", "PE"])
            )

        return filtered

    # ═════════════════════════════════════════════════════════════
    # Symbol format helper
    # ═════════════════════════════════════════════════════════════

    @staticmethod
    def to_fyers_symbol(exchange: str, tradingsymbol: str) -> str:
        """Convert to Fyers symbol format.

        Args:
            exchange: Exchange code ('NSE', 'BSE', 'MCX', etc.).
            tradingsymbol: Trading symbol ('RELIANCE-EQ', 'NIFTY24AUGFUT').

        Returns:
            Fyers format string like 'NSE:RELIANCE-EQ'.
        """
        return f"{exchange}:{tradingsymbol}"

    @staticmethod
    def from_fyers_symbol(fyers_symbol: str) -> tuple[str, str]:
        """Parse a Fyers symbol into exchange and tradingsymbol.

        Args:
            fyers_symbol: Fyers format like 'NSE:RELIANCE-EQ'.

        Returns:
            Tuple of (exchange, tradingsymbol).
        """
        parts = fyers_symbol.split(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", fyers_symbol

    # ═════════════════════════════════════════════════════════════
    # Segment info
    # ═════════════════════════════════════════════════════════════

    def get_loaded_segments(self) -> list[str]:
        """Return list of currently loaded segment names."""
        return list(self._dataframes.keys())

    def get_contract_count(self, segment: str) -> int:
        """Return number of contracts loaded for a segment."""
        df = self._dataframes.get(segment)
        return len(df) if df is not None else 0


__all__ = ["FyersContracts", "MASTER_CONTRACT_URLS"]
