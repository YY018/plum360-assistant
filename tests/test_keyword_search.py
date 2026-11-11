"""Tests for BM25 keyword ranking and hybrid rank fusion."""

import unittest

from plum360_assistant.keyword_search import KeywordIndex, reciprocal_rank_fusion, tokenize


class TokenizeTests(unittest.TestCase):
    def test_drops_stopwords_and_normalizes_plurals(self) -> None:
        self.assertEqual(tokenize("How much air does the air trap allow?"), ["much", "air", "air", "trap", "allow"])
        self.assertEqual(tokenize("The trap allows 1 mL"), ["trap", "allow", "1", "ml"])
        self.assertEqual(tokenize("hard limits"), ["hard", "limit"])

    def test_keeps_numbers_codes_and_decimals(self) -> None:
        self.assertEqual(tokenize("E301 at 0.5 mL/hr"), ["e301", "0.5", "ml", "hr"])


class KeywordIndexTests(unittest.TestCase):
    def test_rare_exact_terms_rank_first(self) -> None:
        index = KeywordIndex([
            {"text": "Air in line alarm. Air bubbles. Air sensors detect air."},
            {"text": "The air trap allows 1 mL of air before the alarm."},
            {"text": "Cleaning the infuser with approved solutions."},
        ])
        ranking = index.search("How much air does the air trap allow?", top_k=3)
        self.assertEqual(ranking[0][0], 1)
        self.assertNotIn(2, [position for position, _ in ranking])


class FusionTests(unittest.TestCase):
    def test_each_lists_top_item_is_kept(self) -> None:
        vector = ["v1", "shared", "v3", "v4"]
        keyword = ["k1", "v4", "shared", "v3"]
        fused = reciprocal_rank_fusion([vector, keyword])
        self.assertEqual(set(fused[:2]), {"v1", "k1"})
        self.assertEqual(fused[2], "shared")

    def test_single_list_keeps_its_order(self) -> None:
        self.assertEqual(reciprocal_rank_fusion([["a", "b", "c"], []]), ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
