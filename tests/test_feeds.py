import unittest
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from radar.sources import feeds

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Hello &amp; welcome</title><link>https://a.test/1</link>
<description>&lt;p&gt;Body text&lt;/p&gt;</description>
<pubDate>Tue, 04 Nov 2026 10:00:00 +0000</pubDate><guid>g1</guid></item>
<item><title></title><link>https://a.test/2</link><pubDate>Tue, 04 Nov 2026 10:00:00 +0000</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>v1.2.3</title><link rel="alternate" href="https://g.test/r/1"/>
<id>tag:g.test,1</id><updated>2026-11-04T09:00:00Z</updated><content>notes</content></entry></feed>"""


class ParseFeedTests(unittest.TestCase):
    def test_rss_fields_and_html_cleaning(self):
        entries = feeds.parse_feed(RSS)
        self.assertEqual(entries[0]["title"], "Hello & welcome")
        self.assertEqual(entries[0]["summary"], "Body text")
        self.assertEqual(entries[0]["id"], "g1")
        self.assertEqual(entries[0]["published"], datetime(2026, 11, 4, 10, tzinfo=timezone.utc))

    def test_atom_link_and_date(self):
        entry = feeds.parse_feed(ATOM)[0]
        self.assertEqual(entry["link"], "https://g.test/r/1")
        self.assertEqual(entry["published"], datetime(2026, 11, 4, 9, tzinfo=timezone.utc))

    def test_items_missing_a_required_field_are_counted_not_silently_dropped(self):
        result = feeds._to_signals(feeds.parse_feed(RSS), "rss:t", "news", "", "q",
                                   datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(len(result.signals), 1)
        self.assertEqual(result.skipped, 1)

    def test_old_items_are_filtered_by_since(self):
        result = feeds._to_signals(feeds.parse_feed(RSS), "rss:t", "news", "", "q",
                                   datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertEqual(result.signals, [])

    def test_unknown_document_type_raises(self):
        with self.assertRaises(ValueError):
            feeds.parse_feed(b"<html><body/></html>")

    def test_malformed_xml_raises(self):
        with self.assertRaises(ET.ParseError):
            feeds.parse_feed(b"<rss><channel>")


if __name__ == "__main__":
    unittest.main()
