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

## Planning

[planning.md](planning.md) documents the design ahead of the code: what each tool takes and returns, how the planning loop decides what to call next, how state passes between tools, and how each failure mode is handled.
