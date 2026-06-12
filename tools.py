"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

# Default Groq chat model used by the LLM-backed tools.
MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Filter by price ceiling and size (when provided).
    candidates = []
    for item in listings:
        if max_price is not None and item.get("price", 0) > max_price:
            continue
        if size is not None:
            item_size = (item.get("size") or "").lower()
            if size.strip().lower() not in item_size:
                continue
        candidates.append(item)

    # 2. Score remaining listings by keyword overlap with the description.
    #    Each query keyword that appears in the listing's searchable text
    #    contributes to the score. Style tags and title matches count extra
    #    since they are the strongest relevance signals.
    keywords = [w for w in description.lower().split() if w]

    scored = []
    for item in candidates:
        tags = " ".join(item.get("style_tags", []))
        haystack = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            tags,
            item.get("brand") or "",
        ]).lower()

        score = 0
        title_text = item.get("title", "").lower()
        tag_text = tags.lower()
        for kw in keywords:
            if kw in haystack:
                score += 1
                if kw in tag_text:
                    score += 2
                if kw in title_text:
                    score += 1

        # 3. Drop listings with no keyword overlap at all.
        if score > 0:
            scored.append((score, item))

    # 4. Sort by score, highest first, and return just the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    # Describe the thrifted item the user is considering.
    item_desc = (
        f"- Title: {new_item.get('title', 'Unknown item')}\n"
        f"- Category: {new_item.get('category', 'n/a')}\n"
        f"- Colors: {', '.join(new_item.get('colors', [])) or 'n/a'}\n"
        f"- Style: {', '.join(new_item.get('style_tags', [])) or 'n/a'}\n"
        f"- Condition: {new_item.get('condition', 'n/a')}"
    )

    items = wardrobe.get("items", []) if wardrobe else []

    if not items:
        # Empty wardrobe → general styling advice instead of failing.
        prompt = (
            "A shopper is considering this secondhand item but hasn't entered "
            "any wardrobe items yet:\n\n"
            f"{item_desc}\n\n"
            "Give general styling advice for this piece: what kinds of items "
            "pair well with it, what vibe/occasions it suits, and 1-2 concrete "
            "outfit ideas using common wardrobe staples. Keep it friendly and "
            "practical, around 3-5 sentences."
        )
    else:
        # Format the user's wardrobe so the LLM can reference specific pieces.
        wardrobe_lines = []
        for it in items:
            colors = ", ".join(it.get("colors", []))
            tags = ", ".join(it.get("style_tags", []))
            detail = f"  ({colors})" if colors else ""
            if tags:
                detail += f" [{tags}]"
            wardrobe_lines.append(f"- {it.get('name', 'item')}{detail}")
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            "A shopper is considering this secondhand item:\n\n"
            f"{item_desc}\n\n"
            "Here is their current wardrobe:\n"
            f"{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfits that pair the secondhand item with "
            "SPECIFIC pieces named from their wardrobe above. For each outfit, "
            "name the pieces and add a short practical styling tip (e.g. how to "
            "tuck, cuff, layer, or accessorize). Keep it friendly and concise."
        )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a thoughtful personal stylist who gives specific, "
                    "wearable outfit advice in a warm, casual tone."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty / whitespace-only outfit suggestion.
    if not outfit or not outfit.strip():
        return (
            "Could not generate a fit card because no outfit suggestion "
            "was provided."
        )

    client = _get_groq_client()

    title = new_item.get("title", "this thrifted find")
    price = new_item.get("price")
    price_text = f"${price:g}" if price is not None else "a steal"
    platform = new_item.get("platform", "secondhand")

    prompt = (
        f"Here is a thrifted item and an outfit built around it.\n\n"
        f"Item: {title}\n"
        f"Price: {price_text}\n"
        f"Found on: {platform}\n\n"
        f"Outfit suggestion:\n{outfit}\n\n"
        "Write a short, shareable OOTD-style caption (2-4 sentences) for a "
        "social post about this find. Make it sound like a real person wrote "
        "it — casual, a little hyped, not a product description. Mention the "
        f"item name, the price ({price_text}), and the platform ({platform}) "
        "naturally, once each. Capture the outfit's vibe in specific terms. "
        "A couple of tasteful emojis or hashtags are fine. Caption only — no "
        "preamble or quotation marks."
    )

    # 2 & 3. Higher temperature so captions feel fresh and vary per run.
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You write punchy, authentic social media captions for "
                    "thrift and secondhand fashion finds."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1.0,
    )

    return response.choices[0].message.content.strip()
