"""Devanagari to Latin letters, the way Hindi lyrics are usually written
in Latin ("Hinglish"): कदम बढ़ा ले -> Kadam badha le. Readable rather than
scholarly (no diacritics), with the inherent "a" left out where it isn't
said: at the end of a word, and between two sounded syllables."""
import re

VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e", "ऐ": "ai",
          "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e"}
MATRAS = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
          "ौ": "au", "ॉ": "o", "ॅ": "e"}
CONSONANTS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
              "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
              "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
              "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
              # the dotted letters, as single characters (U+0958..U+095F)
              "\u0958": "q", "\u0959": "kh", "\u095a": "gh", "\u095b": "z", "\u095c": "d", "\u095d": "dh",
              "\u095e": "f", "\u095f": "y"}
# Words people spell their own way in Hinglish
WORDS = {"में": "mein", "हैं": "hain", "मैं": "main", "नहीं": "nahin", "क्यों": "kyun", "यहाँ": "yahan", "वहाँ": "wahan",
         "कहाँ": "kahan", "हूँ": "hoon", "तू": "tu", "तुम्हें": "tumhein", "तुझे": "tujhe", "मुझे": "mujhe"}
NUKTA = "़"
NUKTA_FORMS = {"क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f"}
HALANT = "्"
SIGNS = {"ं": "n", "ँ": "n", "ः": "h", "ॐ": "om", "।": ".", "॥": ".", "ऽ": ""}
DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def has_devanagari(text):
    return bool(DEVANAGARI.search(text or ""))


def _word(w):
    import unicodedata
    w = unicodedata.normalize("NFC", w)
    if w in WORDS:
        return WORDS[w]
    out = []   # list of [latin, has_inherent_a]
    i = 0
    while i < len(w):
        ch = w[i]
        nxt = w[i + 1] if i + 1 < len(w) else ""
        if ch in CONSONANTS:
            lat = CONSONANTS[ch]
            if nxt == NUKTA:
                lat = NUKTA_FORMS.get(ch, lat)
                i += 1
                nxt = w[i + 1] if i + 1 < len(w) else ""
            if nxt == HALANT:
                out.append([lat, False])
                i += 2
                continue
            if nxt in MATRAS:
                out.append([lat + MATRAS[nxt], False])
                i += 2
                continue
            out.append([lat, True])   # the inherent "a", decided below
        elif ch in VOWELS:
            out.append([VOWELS[ch], False])
        elif ch in MATRAS:   # a stray vowel sign
            out.append([MATRAS[ch], False])
        elif ch in SIGNS:
            if out and SIGNS[ch] == "n" and out[-1][1]:
                out[-1] = [out[-1][0] + "a", False]   # कं -> kan
            out.append([SIGNS[ch], False])
        elif ch in DIGITS:
            out.append([DIGITS[ch], False])
        elif ch == NUKTA or ch == HALANT:
            pass
        else:
            out.append([ch, False])
        i += 1
    # The inherent "a" isn't said at the end of a word (कदम: kadam), nor in a
    # middle consonant between two sounded syllables (सकते: sakte, सजना: sajna).
    n = len(out)

    def ends_open(k):   # the sound before ends in a vowel, or a nasal after one (रं: ran)
        lat, inherent = out[k]
        return inherent or lat[-1:] in "aeiou" or lat == "n" and k > 0 and (out[k - 1][1] or out[k - 1][0][-1:] in "aeiou")

    def sounded(k):     # the next consonant has a vowel that's said
        lat, inherent = out[k]
        return (inherent and k != n - 1) or (not inherent and lat[-1:] in "aeiou")
    for k, (lat, inherent) in enumerate(out):
        if not inherent:
            continue
        if k == n - 1:
            if n == 1:
                out[k][0] = lat + "a"   # a one-letter word keeps it (न: na)
            continue
        if not (0 < k and ends_open(k - 1) and sounded(k + 1) and out[k + 1][0][:1].isalpha()):
            out[k][0] = lat + "a"
    word = "".join(c[0] for c in out)
    word = re.sub(r"ee$", "i", word)          # ही: hi, ख़ाली: khali
    word = re.sub(r"aa$", "a", word)          # आजा: aaja, तेरा: tera
    word = re.sub(r"eenh?$", "in", word)      # नहीं: nahin
    return word


def to_latin(text):
    """Devanagari words in text, written in Latin letters; the rest as is."""
    def conv(m):
        return _word(m.group(0))
    out = re.sub(r"[ऀ-ॿ]+", conv, text or "")
    # a capital at the start of each line (after an LRC timestamp), like typed lyrics
    return re.sub(r"(?m)^((?:\[[^\]]*\])*\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
