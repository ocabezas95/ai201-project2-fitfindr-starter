"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.

    TODO:
        1. Guard against an empty query (return early with an error message).
        2. Select the wardrobe based on wardrobe_choice.
        3. Call run_agent() with the query and selected wardrobe.
        4. If session["error"] is set, return the error in the first panel
           and empty strings for the other two.
        5. Otherwise, format session["selected_item"] into a readable listing_text
           string and return it along with session["outfit_suggestion"] and
           session["fit_card"].
    """
    # 1. Guard against an empty query.
    if not user_query or not user_query.strip():
        return "Please enter what you're looking for.", "", ""

    # 2. Select the wardrobe based on the radio choice.
    if wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    # 3. Run the agent.
    session = run_agent(query=user_query.strip(), wardrobe=wardrobe)

    # 4. Early-termination path: show the error in the first panel only.
    if session["error"]:
        return session["error"], "", ""

    # 5. Success path: format the selected listing for the first panel.
    item = session["selected_item"]
    price = item.get("price")
    price_text = f"${price:g}" if price is not None else "n/a"
    brand = item.get("brand") or "Unbranded"
    listing_text = (
        f"{item.get('title', 'Untitled')}\n"
        f"\n"
        f"Price:     {price_text}\n"
        f"Size:      {item.get('size', 'n/a')}\n"
        f"Condition: {item.get('condition', 'n/a')}\n"
        f"Brand:     {brand}\n"
        f"Platform:  {item.get('platform', 'n/a')}\n"
        f"\n"
        f"{item.get('description', '')}"
    )

    return listing_text, session["outfit_suggestion"], session["fit_card"]


def _clear_outputs() -> tuple[str, str, str]:
    """Blank the three panels when a new query is submitted, so stale results
    don't linger while the LLM tools run."""
    return "", "", ""


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

# Give the fit-card panel top padding so its floating copy button doesn't
# overlap the first line of caption text.
_CSS = """
.fit-card { padding-top: 1.6rem; }
"""


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row(equal_height=True):
            # Listing is compact data; the outfit is long prose and gets the
            # widest column. The fit card sits in between.
            with gr.Column(scale=2):
                gr.Markdown("### 🛍️ Top listing found")
                # Plain fixed-width data — a textbox renders it cleanly.
                listing_output = gr.Textbox(
                    show_label=False,
                    lines=10,
                    interactive=False,
                )
            with gr.Column(scale=3):
                gr.Markdown("### 👗 Outfit idea")
                # LLM output contains markdown (bold headers) — render it.
                outfit_output = gr.Markdown()
            with gr.Column(scale=2):
                gr.Markdown("### ✨ Your fit card")
                # Markdown render + one-click copy for pasting into a post.
                fitcard_output = gr.Markdown(buttons=["copy"], elem_classes=["fit-card"])

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        outputs = [listing_output, outfit_output, fitcard_output]

        # Clear the panels first so old results don't linger while the LLM
        # tools run, then fill them with the new query's results.
        submit_btn.click(fn=_clear_outputs, outputs=outputs).then(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )
        query_input.submit(fn=_clear_outputs, outputs=outputs).then(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    # Gradio 6 takes theme and css on launch() rather than the Blocks constructor.
    demo.launch(theme=gr.themes.Soft(), css=_CSS)
