from datetime import datetime, date
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class SpotPriceRecord(BaseModel):
    """
    Standard Spot Price Record conforming strictly to VoltPulse Specification Section 6.1.
    """
    market: str = Field(..., description="Market identifier (e.g. shandong, shanxi)")
    date: str = Field(..., description="Trade date in ISO format YYYY-MM-DD")
    timestamp: str = Field(..., description="ISO 8601 interval start timestamp, e.g. 2026-09-01T00:00:00+08:00")
    interval: int = Field(..., description="Interval duration in minutes (e.g. 15 or 60)")
    price_type: Literal["day_ahead", "real_time"] = Field(..., description="Price market clearing type")
    price_rmb_mwh: float = Field(..., description="Cleared price in RMB/MWh")
    source: str = Field(..., description="Official data provider / publication name")
    source_url: str = Field(..., description="Source URL or publication identifier")
    retrieved_at: str = Field(..., description="ISO timestamp when data was fetched/parsed")
    is_simulated: bool = Field(False, description="Strict flag separating real from simulated data")
    schema_version: str = Field("1.0.0", description="Schema version")

    @field_validator("price_rmb_mwh")
    def validate_price_range(cls, v: float) -> float:
        # Sanity check: spot electricity price is bounded in realistic physical markets
        if v < -500.0 or v > 5000.0:
            raise ValueError(f"Extreme electricity price detected out of physical bounds: {v} RMB/MWh")
        return v


# Required DataFrame columns for spot price tables
SPOT_PRICE_COLUMNS = [
    "market",
    "date",
    "timestamp",
    "interval",
    "price_type",
    "price_rmb_mwh",
    "source",
    "source_url",
    "retrieved_at",
    "is_simulated",
    "schema_version"
]
