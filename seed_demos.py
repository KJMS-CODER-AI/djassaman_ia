"""
Remplit la base avec 6 configurations de demo pretes a tester.
"""

import database


def vider_donnees_demo():
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entreprises")
    conn.commit()
    conn.close()


def seed():
    database.init_db()

    # ============================================================
    # 1. RESTAURANT
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="restaurant",
        nom="Royal Food",
        secteur="Restaurant",
        type_activite="commande",
        ton="chaleureux, familier, utilise des emojis avec moderation",
        description="Restaurant ivoirien specialise en pizzas, burgers et plats locaux, livraison a domicile.",
        message_accueil="Bonjour  Bienvenue chez Royal Food ! Que puis-je vous servir aujourd'hui ?",
    )
    items_restaurant = [
        ("Pizza Margherita", "Tomate, mozzarella, basilic", "Pizzas", 4500),
        ("Pizza Pepperoni", "Tomate, mozzarella, pepperoni", "Pizzas", 5500),
        ("Pizza 4 Fromages", "Mozzarella, gorgonzola, chevre, parmesan", "Pizzas", 6000),
        ("Burger Classic", "Steak, cheddar, salade, tomate, oignon", "Burgers", 3500),
        ("Burger Double", "Double steak, double cheddar", "Burgers", 4800),
        ("Attieke Poisson", "Attieke, poisson braise, sauce tomate", "Plats locaux", 3000),
        ("Alloco Poulet", "Bananes plantain frites, poulet braise", "Plats locaux", 3200),
        ("Coca-Cola 33cl", "Boisson gazeuse", "Boissons", 1000),
        ("Fanta 33cl", "Boisson gazeuse", "Boissons", 1000),
        ("Eau minerale", "50cl", "Boissons", 500),
    ]
    for nom, desc, cat, prix in items_restaurant:
        database.ajouter_item_catalogue("restaurant", nom, desc, cat, prix)

    faq_restaurant = [
        ("Quels sont vos horaires ?", "Nous sommes ouverts tous les jours de 11h a 23h."),
        ("Livrez-vous partout a Abidjan ?", "Oui, nous livrons dans toutes les communes d'Abidjan. Les frais varient selon la distance."),
        ("Combien de temps prend une livraison ?", "En moyenne 25 a 35 minutes selon votre zone."),
        ("Acceptez-vous le paiement mobile money ?", "Oui, nous acceptons Orange Money, MTN Money et Wave, ainsi que le paiement a la livraison."),
    ]
    for q, r in faq_restaurant:
        database.ajouter_faq("restaurant", q, r)

    # ============================================================
    # 2. BOUTIQUE
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="boutique",
        nom="Ivoire Style",
        secteur="Boutique (mode & chaussures)",
        type_activite="commande",
        ton="dynamique, tendance, chaleureux",
        description="Boutique de vetements et chaussures tendance, hommes et femmes.",
        message_accueil="Bonjour  Bienvenue chez Ivoire Style ! Vous cherchez quelque chose en particulier ?",
    )
    items_boutique = [
        ("Basket Sneaker Blanche", "Pointures 38 a 45", "Chaussures", 15000),
        ("Basket Sneaker Noire", "Pointures 38 a 45", "Chaussures", 15000),
        ("Chaussure de ville Homme", "Cuir noir, pointures 40 a 45", "Chaussures", 22000),
        ("Sandale Femme", "Disponible en plusieurs coloris", "Chaussures", 12000),
        ("T-shirt Coton", "Disponible en S, M, L, XL", "Vetements", 4500),
        ("Robe Wax", "Motifs africains, tailles 36 a 44", "Vetements", 18000),
        ("Chemise Homme", "Coupe slim, plusieurs coloris", "Vetements", 9000),
        ("Jean Slim", "Homme et Femme, tailles 28 a 38", "Vetements", 13000),
    ]
    for nom, desc, cat, prix in items_boutique:
        database.ajouter_item_catalogue("boutique", nom, desc, cat, prix)

    faq_boutique = [
        ("Puis-je echanger un article ?", "Oui, sous 7 jours avec l'etiquette et le recu, article non porte."),
        ("Livrez-vous en dehors d'Abidjan ?", "Oui, via nos partenaires transporteurs, sous 2 a 5 jours selon la ville."),
        ("Avez-vous une boutique physique ?", "Oui, a Cocody Angre, ouverte du lundi au samedi de 9h a 19h."),
    ]
    for q, r in faq_boutique:
        database.ajouter_faq("boutique", q, r)

    # ============================================================
    # 3. CLINIQUE
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="clinique",
        nom="Clinique Sainte Marie",
        secteur="Clinique medicale",
        type_activite="rendez_vous",
        ton="professionnel, rassurant, empathique",
        description="Clinique polyvalente : cardiologie, pediatrie, gynecologie, medecine generale.",
        message_accueil="Bonjour  Bienvenue a la Clinique Sainte Marie. Comment puis-je vous aider aujourd'hui ?",
    )
    creneaux_clinique = [
        ("Consultation Cardiologue", "Mardi 14 juillet", "10:00"),
        ("Consultation Cardiologue", "Mardi 14 juillet", "15:00"),
        ("Consultation Cardiologue", "Mercredi 15 juillet", "09:00"),
        ("Consultation Pediatre", "Mardi 14 juillet", "11:00"),
        ("Consultation Pediatre", "Jeudi 16 juillet", "10:00"),
        ("Consultation Gynecologue", "Mercredi 15 juillet", "14:00"),
        ("Consultation Medecine Generale", "Lundi 13 juillet", "09:00"),
        ("Consultation Medecine Generale", "Lundi 13 juillet", "16:00"),
    ]
    for libelle, jour, heure in creneaux_clinique:
        database.ajouter_creneau("clinique", libelle, jour, heure)

    faq_clinique = [
        ("Quels documents apporter ?", "Votre carte d'identite, carnet de sante si vous en avez un, et votre carte d'assurance/mutuelle."),
        ("Les urgences sont-elles prises en charge ?", "Oui, notre service d'urgence est ouvert 24h/24. Pour les urgences vitales, appelez directement le numero d'urgence."),
        ("Acceptez-vous les mutuelles ?", "Oui, nous travaillons avec la plupart des mutuelles et assurances locales."),
    ]
    for q, r in faq_clinique:
        database.ajouter_faq("clinique", q, r)

    # ============================================================
    # 4. CABINET D'AVOCAT
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="avocat",
        nom="Cabinet Kouassi & Associes",
        secteur="Cabinet d'avocat",
        type_activite="rendez_vous",
        ton="formel, precis, rassurant",
        description="Cabinet d'avocats specialise en droit des affaires, droit de la famille et droit du travail.",
        message_accueil="Bonjour, bienvenue au Cabinet Kouassi & Associes. Comment pouvons-nous vous accompagner ?",
    )
    creneaux_avocat = [
        ("Consultation Droit des affaires", "Lundi 13 juillet", "09:00"),
        ("Consultation Droit des affaires", "Mercredi 15 juillet", "14:00"),
        ("Consultation Droit de la famille", "Mardi 14 juillet", "10:00"),
        ("Consultation Droit du travail", "Jeudi 16 juillet", "11:00"),
        ("Consultation Droit du travail", "Vendredi 17 juillet", "09:00"),
    ]
    for libelle, jour, heure in creneaux_avocat:
        database.ajouter_creneau("avocat", libelle, jour, heure)

    faq_avocat = [
        ("Quel est le tarif d'une premiere consultation ?", "La premiere consultation est facturee 25 000 FCFA, elle dure environ 45 minutes."),
        ("Puis-je consulter a distance ?", "Oui, nous proposons des consultations par visioconference sur demande."),
        ("Quels documents preparer pour un litige de travail ?", "Votre contrat de travail, vos bulletins de salaire, et tout document lie au litige (courriers, avertissements, etc.)."),
    ]
    for q, r in faq_avocat:
        database.ajouter_faq("avocat", q, r)

    # ============================================================
    # 5. CABINET DENTAIRE
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="dentiste",
        nom="Cabinet Dentaire Sourire+",
        secteur="Cabinet dentaire",
        type_activite="rendez_vous",
        ton="chaleureux, rassurant, simple",
        description="Cabinet dentaire : soins generaux, detartrage, orthodontie, blanchiment.",
        message_accueil="Bonjour  Bienvenue au Cabinet Sourire+. Vous souhaitez prendre rendez-vous ?",
    )
    creneaux_dentiste = [
        ("Detartrage", "Lundi 13 juillet", "10:00"),
        ("Detartrage", "Mardi 14 juillet", "15:00"),
        ("Consultation generale", "Mercredi 15 juillet", "09:00"),
        ("Consultation Orthodontie", "Jeudi 16 juillet", "14:00"),
        ("Blanchiment dentaire", "Vendredi 17 juillet", "11:00"),
    ]
    for libelle, jour, heure in creneaux_dentiste:
        database.ajouter_creneau("dentiste", libelle, jour, heure)

    faq_dentiste = [
        ("Le detartrage est-il douloureux ?", "Non, c'est un soin indolore realise sous anesthesie locale si necessaire."),
        ("Combien coute une consultation generale ?", "La consultation generale est a 10 000 FCFA."),
        ("Traitez-vous les urgences dentaires ?", "Oui, nous reservons des creneaux d'urgence chaque jour, appelez-nous directement."),
    ]
    for q, r in faq_dentiste:
        database.ajouter_faq("dentiste", q, r)

    # ============================================================
    # 6. AUTRE (fallback generique)
    # ============================================================
    database.creer_ou_maj_entreprise(
        id="autre",
        nom="Votre Entreprise",
        secteur="Secteur personnalise",
        type_activite="generique",
        ton="professionnel et adaptable",
        description="Configuration generique : repond aux questions et collecte les besoins du client, sans catalogue ni agenda predefinis.",
        message_accueil="Bonjour Bienvenue ! Je suis l'assistant IA de cette entreprise. Comment puis-je vous aider ?",
    )
    faq_autre = [
        ("Que peux-tu faire ?", "Je peux repondre a vos questions, comprendre vos besoins, et transmettre votre demande a un conseiller si necessaire."),
    ]
    for q, r in faq_autre:
        database.ajouter_faq("autre", q, r)

    print("6 configurations de demo creees : restaurant, boutique, clinique, avocat, dentiste, autre")


if __name__ == "__main__":
    seed()