"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# Standard clothing sizes, longest first so "XXL" matches before "XL"/"L".
_SIZE_TOKENS = ["XXS", "XS", "XXL", "XL", "S", "M", "L"]


def _parse_query(query: str) -> dict:
    """
    Extract a description, size, and max_price from a natural language query
    using regex / string matching (no LLM call needed for this step).

    Returns a dict with keys: description (str), size (str | None),
    max_price (float | None).
    """
    text = query.strip()
    working = text  # we strip matched phrases out to leave a clean description

    # max_price: only treat a number as a price when it carries a price signal —
    # either a keyword ("under $30", "below 30", "max $40") or a "$" sign ("$30").
    # This avoids misreading "90s" or "501" as a budget.
    max_price = None
    price_match = re.search(
        r"(?:under|below|less than|max(?:imum)?|up to|cheaper than|<)\s*\$?\s*(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    ) or re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if price_match:
        max_price = float(price_match.group(1))
        working = working.replace(price_match.group(0), " ")

    # size: prefer an explicit "size M" / "size: L" / "size 32"; fall back to a
    # standalone letter token. Accept known letter sizes or a numeric size.
    size = None
    explicit = re.search(r"\bsize\s*:?\s*([A-Za-z0-9]+)", text, flags=re.IGNORECASE)
    if explicit:
        candidate = explicit.group(1).upper()
        if candidate in _SIZE_TOKENS or candidate.isdigit():
            size = candidate
        working = re.sub(
            r"\bsize\s*:?\s*[A-Za-z0-9]+", " ", working, flags=re.IGNORECASE
        )
    else:
        for token in _SIZE_TOKENS:
            # standalone size token, surrounded by word boundaries
            if re.search(rf"\b{token}\b", working):
                size = token
                working = re.sub(rf"\b{token}\b", " ", working, count=1)
                break

    # description: leftover text, with common filler phrases removed.
    description = re.sub(
        r"\b(looking for|i want|i need|find me|show me|a|an|some|the|for|in)\b",
        " ",
        working,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"[^\w\s'-]", " ", description)  # drop $, punctuation
    description = re.sub(r"\s+", " ", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session — the single source of truth for this interaction.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into search parameters.
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search the listings.
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # Empty-result short-circuit: do NOT proceed to the LLM tools.
    if len(results) == 0:
        constraints = []
        if parsed["size"]:
            constraints.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            constraints.append(f"under ${parsed['max_price']:g}")
        extra = f" ({', '.join(constraints)})" if constraints else ""
        session["error"] = (
            f"No listings matched '{parsed['description']}'{extra}. "
            "Try widening your budget, relaxing the size, or using different "
            "keywords."
        )
        return session

    # Step 4: select the top (most relevant) match.
    session["selected_item"] = results[0]

    # Step 5: suggest an outfit using the selected item and the wardrobe.
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )

    # Step 6: turn the outfit into a shareable fit card.
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: done — fit_card is populated, error is still None.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
