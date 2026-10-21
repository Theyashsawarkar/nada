"""Tests for the parts that don't need MPD, GTK or the network."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nada import lyrics, youtube  # noqa: E402
from nada.mpd import quote, split_items  # noqa: E402


class YouTubeTitles(unittest.TestCase):
    def test_clean_film_titles(self):
        self.assertEqual(youtube.clean("ROCKSTAR: Kun Faya Kun (Full Video Song) | Ranbir Kapoor | A.R. Rahman", "T-Series"),
                         ("ROCKSTAR: Kun Faya Kun", "T-Series"))

    def test_clean_artist_dash_title(self):
        self.assertEqual(youtube.clean("Coldplay - Yellow (Official Video)", "Coldplay"), ("Yellow", "Coldplay"))

    def test_clean_tight_bars(self):
        self.assertEqual(youtube.clean("Tum Hi Ho|Arijit Singh|Aashiqui 2", "Sankalp")[0], "Tum Hi Ho")

    def test_credits(self):
        c = youtube.credits("ROCKSTAR: Kun Faya Kun (Full Video Song) | Ranbir Kapoor | A.R. Rahman, Javed Ali, Mohit Chauhan")
        self.assertEqual(c["movie"], "ROCKSTAR")
        self.assertEqual(c["cast"], "Ranbir Kapoor")
        self.assertEqual(c["people"], "A.R. Rahman, Javed Ali, Mohit Chauhan")

    def test_video_id(self):
        for url in ("https://www.youtube.com/watch?v=T94PHkuydcw&list=RD", "https://youtu.be/T94PHkuydcw",
                    "https://youtube.com/shorts/T94PHkuydcw", "T94PHkuydcw"):
            self.assertEqual(youtube.video_id(url), "T94PHkuydcw", url)
        self.assertIsNone(youtube.video_id("https://example.com/song.mp3"))

    def test_views_and_age(self):
        self.assertEqual(youtube.views(536717711), "536.7M views")
        self.assertEqual(youtube.views(1200), "1.2K views")
        self.assertEqual(youtube.views(0), "")
        self.assertEqual(youtube.ago(time.time() - 3 * 86400), "3 days ago")
        self.assertEqual(youtube.ago(time.time() - 40 * 86400), "1 month ago")
        self.assertEqual(youtube.ago(time.time() - 800 * 86400), "2 years ago")
        self.assertEqual(youtube.ago(0), "")


class Lyrics(unittest.TestCase):
    def test_parse_lrc(self):
        r = lyrics.parse("[ar:Someone]\n[00:12.50]first line\n[00:05.00][01:00.00]twice\n[offset:+500]")
        self.assertTrue(r["synced"])
        self.assertEqual([t for t, _ in r["lines"]], [5.0, 12.5, 60.0])

    def test_parse_plain(self):
        r = lyrics.parse("\n\nline one\nline two\n")
        self.assertFalse(r["synced"])
        self.assertEqual([x for _, x in r["lines"]][:2], ["line one", "line two"])

    def test_variants(self):
        v = lyrics.variants("Arijit Singh singing Tum Hi Ho Live (Aashiqui 2)")
        self.assertIn("Tum Hi Ho", v)
        self.assertEqual(lyrics.variants("ROCKSTAR: Kun Faya Kun")[0], "Kun Faya Kun")


class Protocol(unittest.TestCase):
    def test_quote(self):
        self.assertEqual(quote('a "b" \\c'), '"a \\"b\\" \\\\c"')

    def test_split_items(self):
        items = split_items([("file", "a.mp3"), ("Title", "A"), ("file", "b.mp3"), ("Title", "B")])
        self.assertEqual([i["Title"] for i in items], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
