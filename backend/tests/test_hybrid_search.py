from app.services.hybrid_search import bm25_rank, reciprocal_rank_fusion


def test_bm25_rank_favors_exact_keyword_match():
    corpus = [
        "Le chat dort sur le canape toute la journee.",
        "La facture numero INV-2026-0042 est due le 15 mars.",
        "Les chiens aiment jouer dans le jardin.",
    ]
    ranking = bm25_rank("facture INV-2026-0042", corpus)
    assert ranking[0] == 1


def test_bm25_rank_empty_corpus():
    assert bm25_rank("peu importe", []) == []


def test_reciprocal_rank_fusion_boosts_items_ranked_high_in_both_lists():
    vector_ranking = ["a", "b", "c", "d"]
    bm25_ranking = ["c", "a", "d", "b"]
    fused = reciprocal_rank_fusion([vector_ranking, bm25_ranking])
    # "a" est 1er en vectoriel et 2e en BM25 : doit dominer le classement fusionne
    assert fused[0] == "a"


def test_reciprocal_rank_fusion_item_missing_from_one_list_still_included():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert set(fused) == {"a", "b", "c"}
    # "b" apparait en tete des deux listes : doit arriver premier
    assert fused[0] == "b"


def test_reciprocal_rank_fusion_empty_rankings():
    assert reciprocal_rank_fusion([[], []]) == []
