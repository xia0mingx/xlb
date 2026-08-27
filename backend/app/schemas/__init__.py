"""Pydantic response/request models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BrandOut(BaseModel):
    id: int
    name: str
    slug: str


class ConcernOut(BaseModel):
    key: str
    label: str
    description: str | None = None


class IngredientOut(BaseModel):
    position: int
    inci_name: str
    common_name: str | None = None
    function: str | None = None
    is_active: bool = False
    is_irritant: bool = False
    comedogenic_rating: int | None = None
    active_group: str | None = None
    description: str | None = None
    known: bool = True
    is_prominent: bool = False
    # "natural" | "nature_identical" | "synthetic" | None when undetermined.
    source: str | None = None


class RetailerPrice(BaseModel):
    retailer: str
    retailer_slug: str
    url: str
    price: float | None = None
    was_price: float | None = None
    currency: str = "USD"
    in_stock: bool = True
    last_scraped_at: datetime | None = None
    is_stale: bool = False
    is_best: bool = False


class PricePoint(BaseModel):
    date: datetime
    price: float


class PriceHistory(BaseModel):
    retailer: str
    retailer_slug: str
    points: list[PricePoint]


class AllergenHit(BaseModel):
    """One ingredient in a product that the user's avoid-list covers."""

    inci_name: str
    common_name: str | None = None
    position: int
    prominent: bool = False
    matched: str
    group_label: str | None = None
    summary: str


class AllergenScreenOut(BaseModel):
    """Result of screening one product. `verdict` is deliberately three-valued:
    a product we could not fully read is `incomplete`, never `clear`."""

    verdict: str = "clear"
    hits: list[AllergenHit] = Field(default_factory=list)
    unrecognized: list[str] = Field(default_factory=list)
    unknown_count: int = 0
    screened: bool = False


class AllergenTermOut(BaseModel):
    query: str
    label: str
    kind: str
    key: str | None = None
    note: str | None = None
    recognized: bool = True
    member_count: int = 0


class AllergenGroupOut(BaseModel):
    key: str
    label: str
    note: str | None = None
    members: list[str] = Field(default_factory=list)
    #: Products in the catalogue this group actually matches. Shown in the UI so
    #: a group that hits nothing does not read as a broken filter.
    product_matches: int = 0


class ProductSummary(BaseModel):
    id: int
    slug: str
    name: str
    brand: str
    category: str
    size_label: str | None = None
    image_url: str | None = None
    best_price: float | None = None
    highest_price: float | None = None
    retailer_count: int = 0
    on_sale: bool = False
    concerns: list[str] = Field(default_factory=list)
    key_actives: list[str] = Field(default_factory=list)
    allergens: AllergenScreenOut | None = None


class ProductAnalysis(BaseModel):
    active_groups: list[str] = Field(default_factory=list)
    max_comedogenic: int = 0
    has_fragrance: bool = False
    has_alcohol: bool = False
    has_essential_oil: bool = False
    known_count: int = 0
    unknown_count: int = 0
    # Provenance breakdown. `unknown_source` is reported separately rather than
    # folded in, so a product we cannot classify does not read as synthetic.
    natural_count: int = 0
    nature_identical_count: int = 0
    synthetic_count: int = 0
    unknown_source_count: int = 0


class ProductDetail(ProductSummary):
    description: str | None = None
    upc: str | None = None
    # Exposed so the page can show a unit price: $46.40 for 100ml is only
    # comparable to $30.00 for 150ml once both are per-millilitre.
    size_value: float | None = None
    size_unit: str | None = None
    ingredients: list[IngredientOut] = Field(default_factory=list)
    analysis: ProductAnalysis = Field(default_factory=ProductAnalysis)
    prices: list[RetailerPrice] = Field(default_factory=list)
    lowest_90d: float | None = None
    highest_90d: float | None = None


class ProductPage(BaseModel):
    items: list[ProductSummary]
    total: int
    page: int
    page_size: int
    pages: int


class DupeOut(BaseModel):
    product: ProductSummary
    similarity: float
    shared_actives: list[str] = Field(default_factory=list)
    savings: float | None = None


class QuizRequest(BaseModel):
    skin_type: str = "normal"
    concerns: list[str] = Field(default_factory=list)
    sensitive: bool = False
    acne_prone: bool = False
    fragrance_free: bool = False
    budget_max: float | None = None
    categories: list[str] = Field(default_factory=list)
    avoid_ingredients: list[str] = Field(default_factory=list)
    limit: int = 12


class Recommendation(BaseModel):
    product: ProductSummary
    score: float
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConflictOut(BaseModel):
    id: str
    severity: str
    title: str
    explanation: str
    guidance: str
    products: list[str] = Field(default_factory=list)


class RoutineOut(BaseModel):
    am: list[ProductSummary] = Field(default_factory=list)
    pm: list[ProductSummary] = Field(default_factory=list)


class ExcludedProduct(BaseModel):
    slug: str
    name: str
    brand: str
    hits: list[AllergenHit] = Field(default_factory=list)


class QuizResponse(BaseModel):
    recommendations: list[Recommendation] = Field(default_factory=list)
    routine: RoutineOut = Field(default_factory=RoutineOut)
    conflicts: list[ConflictOut] = Field(default_factory=list)
    # Products removed outright for containing something the user avoids. Kept
    # separate from `recommendations` so the UI can say what it withheld rather
    # than silently returning a shorter list.
    excluded: list[ExcludedProduct] = Field(default_factory=list)
    allergen_terms: list[AllergenTermOut] = Field(default_factory=list)


class ConflictRequest(BaseModel):
    product_ids: list[int] = Field(default_factory=list)


class FilterOptions(BaseModel):
    categories: list[dict]
    concerns: list[ConcernOut]
    brands: list[BrandOut]
    price_range: dict


class ChatMessage(BaseModel):
    """One prior turn, replayed from the client.

    `role` is constrained to user and assistant on purpose: accepting "system"
    here would let a caller rewrite the assistant's instructions, and accepting
    "tool" would let it fabricate tool results.
    """

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    avoid: list[str] = Field(default_factory=list, max_length=50)
    # What the viewer sees on the page. An unknown code falls back to USD rather
    # than erroring, so a stale localStorage value cannot break the assistant.
    currency: str | None = None


class ChatResponse(BaseModel):
    reply: str
    # Echoed back so the client can persist anything recorded this turn.
    avoid: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
