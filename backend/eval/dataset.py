"""Jeu de questions de référence pour l'évaluation RAGAS. Couvre plusieurs
sujets distincts du document fixture (pour vérifier que la recherche ne
confond pas les sujets) et une question hors-sujet (pour vérifier
l'absence d'hallucination — voir le champ `is_unanswerable`)."""

GOLDEN_SET: list[dict] = [
    {
        "question": "Combien de jours de congés payés par an, et combien de RTT ?",
        "ground_truth": "26 jours de congés payés par an et 10 jours de RTT.",
        "is_unanswerable": False,
    },
    {
        "question": "Combien de jours de télétravail sont autorisés par semaine ?",
        "ground_truth": "3 jours de télétravail par semaine, sous validation du manager.",
        "is_unanswerable": False,
    },
    {
        "question": "Quel est le plafond de remboursement pour un repas d'affaires ?",
        "ground_truth": "60 euros par personne.",
        "is_unanswerable": False,
    },
    {
        "question": "À quelle fréquence le mot de passe professionnel doit-il être changé, "
        "et quelle est sa longueur minimale ?",
        "ground_truth": "Tous les 90 jours, avec un minimum de 12 caractères.",
        "is_unanswerable": False,
    },
    {
        "question": "Quelle est la différence entre l'entretien annuel et l'entretien "
        "professionnel ?",
        "ground_truth": "L'entretien annuel a lieu chaque année (généralement en janvier) "
        "et évalue la performance ; l'entretien professionnel a lieu tous les deux ans "
        "et porte sur les perspectives d'évolution de carrière.",
        "is_unanswerable": False,
    },
    {
        "question": "Quelle est la couleur du logo de l'entreprise ?",
        "ground_truth": "Cette information n'est pas présente dans le document.",
        "is_unanswerable": True,
    },
]
