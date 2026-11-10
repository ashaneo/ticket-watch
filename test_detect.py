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

CLOUDFLARE_BLOCK = "<html><body><h1>Just a moment...</h1></body></html>"


def test_not_open_ignores_carousel_buttons():
    assert check_html(AVENGERS_NOT_OPEN) == (False, "AVENGERS: DOOMSDAY")


def test_open():
    assert check_html(ROCKY_OPEN) == (True, "I PLAY ROCKY")


def test_blocked_page_is_unknown():
    available, _ = check_html(CLOUDFLARE_BLOCK)
    assert available is None
