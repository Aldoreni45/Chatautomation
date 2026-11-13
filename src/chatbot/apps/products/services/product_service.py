
from dataclasses import dataclass
import re

from django.db.models import Q

from apps.products.models import Product, ProductAlias


@dataclass(frozen=True)
class ProductMatchResult:
    status: str
    product: Product | None = None
    matches: tuple = ()
    message: str = ""


def normalize_product_name(value: str) -> str:
    """
    Normalize customer input before matching.

    Example:
        "  BASMATI   Rice " -> "basmati rice"
    """
    if not isinstance(value, str):
        return ""

    value = value.strip().casefold()
    value = re.sub(r"\s+", " ", value)

    return value


def find_product(store_id: int, query: str) -> ProductMatchResult:
    """
    Find an active product belonging to a particular store.

    Matching priority:
        1. Exact product name
        2. Exact product alias
        3. Partial product name or alias

    Returns:
        matched   -> Exactly one product found
        ambiguous -> Multiple products found
        not_found -> No matching product
    """

    search_term = normalize_product_name(query)

    if not search_term:
        return ProductMatchResult(
            status="not_found",
            message="Please provide a valid product name."
        )

    base_products = (
        Product.objects
        .filter(store_id=store_id, is_active=True)
        .select_related("store", "category")
    )

    # STEP 1: Exact product-name matching
    exact_products = base_products.filter(name__iexact=search_term)

    if exact_products.count() == 1:
        return ProductMatchResult(
            status="matched",
            product=exact_products.first(),
            message="Product found by exact name."
        )

    if exact_products.count() > 1:
        return ProductMatchResult(
            status="ambiguous",
            matches=tuple(exact_products),
            message="Multiple products have this name."
        )

    # STEP 2: Exact alias matching
    exact_aliases = ProductAlias.objects.filter(
        product__store_id=store_id,
        product__is_active=True,
        alias__iexact=search_term
    ).select_related("product", "product__store", "product__category")

    alias_products = tuple({
        alias.product.id: alias.product
        for alias in exact_aliases
    }.values())

    if len(alias_products) == 1:
        return ProductMatchResult(
            status="matched",
            product=alias_products[0],
            message="Product found using an alias."
        )

    if len(alias_products) > 1:
        return ProductMatchResult(
            status="ambiguous",
            matches=alias_products,
            message="This alias matches multiple products."
        )

    # STEP 3: Partial matching
    partial_products = base_products.filter(
        Q(name__icontains=search_term)
        | Q(aliases__alias__icontains=search_term)
    ).distinct()

    partial_matches = tuple(partial_products)

    if len(partial_matches) == 1:
        return ProductMatchResult(
            status="matched",
            product=partial_matches[0],
            message="Product found using partial matching."
        )

    if len(partial_matches) > 1:
        return ProductMatchResult(
            status="ambiguous",
            matches=partial_matches,
            message="Multiple products match your request."
        )

    return ProductMatchResult(
        status="not_found",
        message="Sorry, this product was not found in the store."
    )
