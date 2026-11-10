"""Detection tests built from the structure of the two real Scope Cinemas pages."""
from monitor import check_html

SITE_HEADER = '<header><nav><a href="/movies">Movies</a></nav></header>'

ALSO_LIKE_WITH_BUY = """
<section><h1>YOU MAY ALSO LIKE</h1>
  <article><a href="/movies/kotu-sinhala">See More</a>
    <button aria-label="" type="button">Buy Tickets</button></article>
</section>"""

AVENGERS_NOT_OPEN = f"""<body>{SITE_HEADER}<main class="fade-in-page">
<header><h1>AVENGERS: DOOMSDAY </h1><p>Action/Adventure, 2h 45min | PG-13</p>
  <button aria-label="Watch trailer for AVENGERS: DOOMSDAY " type="button">WATCH TRAILER</button>
</header>
<span>Releasing 18 December 2026</span>
{ALSO_LIKE_WITH_BUY}
</main></body>"""

ROCKY_OPEN = f"""<body>{SITE_HEADER}<main class="fade-in-page">
<header><h1>I PLAY ROCKY</h1><p>Drama, 2h 8min</p>
  <button aria-label="Watch trailer for I PLAY ROCKY" type="button">WATCH TRAILER</button>
  <button aria-label="Buy tickets for I PLAY ROCKY" type="button">BUY TICKETS</button>
</header>
{ALSO_LIKE_WITH_BUY}
</main></body>"""

LOADING_MAIN = '<main class="h-screen flex"><img alt="Scope Cinemas Logo"><div class="w-20"></div></main>'

# What the raw server HTML actually looks like: loading fallback first, real page streamed later
STREAMED_NOT_OPEN = f"""<body>{SITE_HEADER}{LOADING_MAIN}
<div hidden id="S:0">{AVENGERS_NOT_OPEN}</div></body>"""
STREAMED_OPEN = f"""<body>{SITE_HEADER}{LOADING_MAIN}
<div hidden id="S:0">{ROCKY_OPEN}</div></body>"""

CLOUDFLARE_BLOCK ="<html><body><h1>Just a moment...</h1></body></html>"


def test_not_open_ignores_carousel_buttons():
    assert check_html(AVENGERS_NOT_OPEN) == (False, "AVENGERS: DOOMSDAY")


def test_open():
    assert check_html(ROCKY_OPEN) == (True, "I PLAY ROCKY")


def test_streamed_not_open():
    assert check_html(STREAMED_NOT_OPEN) == (False, "AVENGERS: DOOMSDAY")


def test_streamed_open():
    assert check_html(STREAMED_OPEN) == (True, "I PLAY ROCKY")


def test_loading_only_is_unknown():
    available, _ = check_html(f"<body>{LOADING_MAIN}</body>")
    assert available is None


def test_blocked_page_is_unknown():
    available, _ = check_html(CLOUDFLARE_BLOCK)
    assert available is None
