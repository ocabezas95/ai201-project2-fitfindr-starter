# FitFindr

FitFindr takes a plain-English request like "vintage graphic tee under $30, size M," finds a matching secondhand listing, and then styles it against your wardrobe and writes a caption you could actually post. It runs as a small Gradio web app backed by a three-tool agent.

## How it works

You type a query and pick a wardrobe. The agent then runs three tools in order, passing results from one to the next through a single `session` dictionary:

1. `search_listings` parses the query into keywords, an optional size, and an optional price cap, then filters and ranks the 40 mock listings by keyword overlap. The top match moves on.
2. `suggest_outfit` asks the LLM to pair that item with specific pieces from your wardrobe. If your wardrobe is empty, it falls back to general styling advice instead.
3. `create_fit_card` turns the outfit into a short, casual caption that mentions the item, its price, and where it's listed.

If the search turns up nothing, the agent stops right there and tells you to widen your budget or relax the size. It never calls the LLM tools with empty input.

The pieces live in three files: [tools.py](tools.py) holds the three tools, [agent.py](agent.py) has the planning loop and the query parser, and [app.py](app.py) is the Gradio interface.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

Then add your Groq API key to a `.env` file in the project root (free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running it

Start the web app:

```bash
python app.py
```

Open the localhost URL it prints (usually http://localhost:7860). Type a query, choose the example or empty wardrobe, and hit "Find it."

You can also run the agent on its own from the command line, which prints a happy-path result and a no-results result:

```bash
python agent.py
```

## The data

`data/listings.json` has 40 mock secondhand listings across tops, bottoms, outerwear, shoes, and accessories, tagged with styles like vintage, y2k, grunge, cottagecore, and streetwear. Each listing carries an `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

`data/wardrobe_schema.json` defines the wardrobe format. It ships with an example wardrobe of 10 items for testing and an empty template that stands in for a brand-new user.

Load either one through the helpers in [utils/data_loader.py](utils/data_loader.py):

```python
from utils.data_loader import load_listings, get_example_wardrobe

listings = load_listings()
wardrobe = get_example_wardrobe()
```

## DEMO
![alt text](images/Screenshot%202026-06-11%20at%209.22.47 PM.png)

## Planning

[planning.md](planning.md) documents the design ahead of the code: what each tool takes and returns, how the planning loop decides what to call next, how state passes between tools, and how each failure mode is handled.

## AI usage

I built this with Claude (through Claude Code), feeding it the specs from planning.md one tool at a time. Here are three places where it helped and where I had to step in.

For `search_listings`, I handed Claude the Tool 1 section of planning.md, the `tools.py` docstring, and a slice of the real `listings.json` so it could see the actual field names. It wrote the keyword-overlap filter that ranks listings and weights matches in the title and style tags higher. Reviewing what it produced, I caught a mistake in my own spec: I'd listed the result fields as `id, title, price, brand, size, condition`, but the real listings also carry `description`, `category`, `style_tags`, `colors`, and `platform`, and the styling tools need those. I corrected the field list in planning.md instead of the code.

The query parser was the one I had to override the most. I gave Claude the Planning Loop and State Management sections and asked for a regex parser rather than an LLM call. Its first pass handled tidy queries fine but fell apart on real ones. It read "90s graphic tee" as a $90 budget, treated "Levi 501" as a $501 budget, and chopped "oversized hoodie" down to "over hoodie" because the size pattern matched the "size" sitting inside "oversized." I made it only count a number as a price when there's a real signal next to it, a keyword like "under" or a literal `$`, and added word boundaries to the size match. Then I ran it against seven query variations before trusting it. The Query parsing note in planning.md records the choice.

The UI had a smaller version of the same story. When I asked Claude to render the outfit and fit-card panels as markdown and add a copy button, its first attempt used `gr.Markdown(show_copy_button=True)`, which crashed on the installed Gradio (6.17.3). I had it read the actual component signature; the working version uses `buttons=["copy"]` and passes `theme` and `css` to `launch()` rather than the `Blocks` constructor.
