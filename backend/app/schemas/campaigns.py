from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_ISO3166_ALPHA2 = re.compile(r"^[A-Z]{2}$")


class CreateCampaignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    geo_iso: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    offer_id: int = Field(..., gt=0)
    domain_id: int = Field(..., gt=0)
    group_id: int = Field(..., gt=0)
    traffic_source_id: int = Field(..., gt=0)
    alias: str | None = Field(None, description="Optional; slug derived from name if omitted")

    @field_validator("geo_iso")
    @classmethod
    def normalize_geo(cls, v: str) -> str:
        code = v.strip().upper()
        if not _ISO3166_ALPHA2.match(code):
            raise ValueError("geo_iso must be a 2-letter ISO country code")
        return code


class OfferWeightInput(BaseModel):
    offer_id: int = Field(..., gt=0)
    weight: int | float | None = Field(
        None,
        ge=0,
        description="Optional weight; normalized to sum 100 if not already integers summing to 100",
    )


class UpdateStreamOffersRequest(BaseModel):
    offers: list[OfferWeightInput] = Field(..., min_length=1)


class CampaignCreateResponse(BaseModel):
    operation_id: int
    campaign_id: int
    streams: list[dict]


class StreamOffersResponse(BaseModel):
    stream_id: int
    offers: list[dict]