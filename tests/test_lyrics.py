"""Lyrics: which source wins, what gets cached (a failure must not be
remembered as "no lyrics"), offsets, and writing Hindi in Latin letters.
No network: every source is replaced by a recorded answer."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp()
os.environ["XDG_CACHE_HOME"] = tmp
from nada import lyrics, translit  # noqa: E402

LRC = "[00:01.00]Kadam badha le\n[00:05.00]Hadon ko mita le"
DEVA = "[00:01.00]कदम बढ़ा ले\n[00:05.00]हदों को मिटा ले"
SONG = {"title": "ROCKSTAR: Kun Faya Kun", "artist": "T-Series", "duration": 381, "yt": "T94PHkuydcw"}


def fresh():
    import shutil
    shutil.rmtree(os.path.join(tmp, "nada"), ignore_errors=True)
    lyrics.CACHE = os.path.join(tmp, "nada")


class Find(unittest.TestCase):
    def setUp(self):
        fresh()

    def patch(self, video=(None, None, None), ysearch=(None, None), get=(None, None), search=(None, None),
              ne=(None, None)):
        def wrap(v):
            def f(*a, **k):
                if isinstance(v, Exception):
                    raise v
                return v
            return f
        return mock.patch.multiple(lyrics, ytmusic_video=wrap(video), ytmusic_search=wrap(ysearch),
                                   lrclib_get=wrap(get), search_lrclib=wrap(search), netease=wrap(ne))

    def test_youtube_music_by_video_wins_and_names_the_song(self):
        meta = {"title": "Kun Faya Kun", "artists": ["A. R. Rahman"], "album": "Rockstar", "year": "2011"}
        with self.patch(video=(meta, LRC, "YouTube Music"), get=("[00:01.00]other", "LRCLIB")):
            r = lyrics.find(SONG)
        self.assertTrue(r["synced"])
        self.assertEqual(r["source"], "YouTube Music")
        self.assertEqual(r["meta"]["artists"], ["A. R. Rahman"])

    def test_a_failure_is_not_cached_as_no_lyrics(self):
        with self.patch(video=lyrics.Unreachable("YouTube Music: timeout"), get=lyrics.Unreachable("lrclib: 503"),
                        search=lyrics.Unreachable("lrclib: 503")):
            with self.assertRaises(lyrics.Unreachable):
                lyrics.find(SONG)
        self.assertIsNone(lyrics.cached(SONG))
        with self.patch(get=(LRC, "LRCLIB")):   # the next try asks again, and finds them
            self.assertTrue(lyrics.find(SONG)["lines"])

    def test_a_real_miss_is_cached_for_a_while(self):
        with self.patch():
            r = lyrics.find(SONG)
        self.assertEqual(r["lines"], [])
        self.assertEqual(lyrics.cached(SONG)["text"], "")
        entry = lyrics.cached(SONG)
        entry["at"] -= lyrics.MISS_TTL + 1
        import json
        with open(lyrics._cache_path(SONG), "w") as f:
            json.dump(entry, f)
        self.assertIsNone(lyrics.cached(SONG))   # stale: asked again

    def test_a_found_source_still_counts_when_another_failed(self):
        with self.patch(video=lyrics.Unreachable("timeout"), get=(LRC, "LRCLIB")):
            r = lyrics.find(SONG)
        self.assertEqual(r["source"], "LRCLIB")

    def test_offset_moves_every_line(self):
        with self.patch(get=(LRC, "LRCLIB")):
            lyrics.find(SONG)
        lyrics.set_offset(SONG, 0.5)
        r = lyrics.result(lyrics.cached(SONG))
        self.assertAlmostEqual(r["lines"][0][0], 1.5)

    def test_hindi_in_latin_letters_or_not(self):
        with self.patch(video=(None, DEVA, "YouTube Music")):
            latin = lyrics.find(SONG, script="latin")
        self.assertEqual(latin["lines"][0][1], "Kadam badha le")
        self.assertTrue(latin["devanagari"])
        native = lyrics.result(lyrics.cached(SONG), "native")
        self.assertEqual(native["lines"][0][1], "कदम बढ़ा ले")

    def test_a_manual_pick_is_kept(self):
        with self.patch():
            lyrics.find(SONG)
        lyrics.use(SONG, {"text": LRC, "source": "LRCLIB"})
        with self.patch(video=(None, "[00:01.00]something else", "YouTube Music")):
            self.assertEqual(lyrics.find(SONG)["lines"][0][1], "Kadam badha le")


class Latin(unittest.TestCase):
    def test_common_words(self):
        for deva, lat in [("कदम बढ़ा ले", "Kadam badha le"), ("तुम ही हो", "Tum hi ho"), ("सजना है मुझे", "Sajna hai mujhe"),
                          ("रंगरेज़ मेरे", "Rangrez mere"), ("चलते चलते", "Chalte chalte"), ("मोहब्बत", "Mohabbat"),
                          ("हम तेरे बिन अब रह नहीं सकते", "Ham tere bin ab rah nahin sakte"), ("न", "Na")]:
            self.assertEqual(translit.to_latin(deva), lat, deva)

    def test_timestamps_and_other_text_stay(self):
        self.assertEqual(translit.to_latin("[00:01.00]दिल (love)"), "[00:01.00]Dil (love)")

    def test_scripts(self):
        self.assertTrue(lyrics.other_script("زہر بݨے، ہاں، تیری"))
        self.assertFalse(lyrics.other_script(DEVA))
        self.assertFalse(lyrics.other_script(LRC))


if __name__ == "__main__":
    unittest.main()
