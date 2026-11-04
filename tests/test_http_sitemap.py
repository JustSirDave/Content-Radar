import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from radar import config, pipeline
from radar.http import FetchError, fetch
from radar.sources import feeds
from radar.store import Store


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/old":
            self.send_response(308)
            self.send_header("Location", "/new")
            self.end_headers()
        elif self.path == "/new":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(self.headers.get("User-Agent", "").encode())
        else:
            self.send_response(403)
            self.end_headers()

    def log_message(self, *args):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_308_redirect_is_followed_and_keeps_the_honest_user_agent(self):
        self.assertEqual(fetch(self.base + "/old").decode(), config.USER_AGENT)

    def test_403_fails_immediately_without_retry(self):
        with mock.patch("radar.http.time.sleep") as sleep:
            with self.assertRaises(FetchError):
                fetch(self.base + "/blocked")
            sleep.assert_not_called()


def _sitemap(paths):
    urls = "".join(
        f"<url><loc>https://www.anthropic.com/{p}</loc><lastmod>2026-10-14T06:32:37.000Z</lastmod></url>"
        for p in paths
    )
    return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'.encode()


class SitemapTests(unittest.TestCase):
    def test_returns_only_news_pages_and_ignores_lastmod(self):
        data = _sitemap(["news/a-post", "news/b-post", "careers", "research/x"])
        with mock.patch.object(feeds, "fetch", return_value=data):
            result = feeds.collect_anthropic_sitemap(datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual([s.title for s in result.signals],
                         ["Anthropic news: a post", "Anthropic news: b post"])

    def test_new_only_baselines_first_then_reports_only_new_pages(self):
        store = Store(":memory:")
        task = pipeline.Task("anthropic_sitemap", feeds.collect_anthropic_sitemap, "vendor", new_only=True)
        now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        with mock.patch.object(feeds, "fetch", return_value=_sitemap(["news/old-1", "news/old-2"])):
            first = pipeline.collect_all(store, [task], now, None)[0]
        self.assertEqual((first["status"], first["items"]), ("ok", 0))
        self.assertIn("baseline", first["note"])

        with mock.patch.object(feeds, "fetch", return_value=_sitemap(["news/old-1", "news/old-2", "news/brand-new"])):
            second = pipeline.collect_all(store, [task], now + timedelta(days=1), None)[0]
        self.assertEqual(second["items"], 1)
        [row] = store.load_window(now)
        self.assertEqual(row["title"], "Anthropic news: brand new")

        with mock.patch.object(feeds, "fetch", return_value=_sitemap(["news/old-1", "news/old-2", "news/brand-new"])):
            third = pipeline.collect_all(store, [task], now + timedelta(days=2), None)[0]
        self.assertEqual(third["items"], 0)  # already reported once


if __name__ == "__main__":
    unittest.main()
