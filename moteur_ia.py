import os
import json
import time
import random
from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from dotenv import load_dotenv

import database

load_dotenv()

client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=45.0, max_retries=0)
MODELE = "openai/gpt-oss-120b"

PANIERS = {}

MOYENS_PAIEMENT = ["Orange Money", "MTN Money", "Wave", "Paiement a la livraison"]

# ---------------------------------------------------------------------------
# THROTTLE : espace les appels Groq pour eviter de taper le rate limit
# (plan gratuit = 8000 tokens/minute). On attend un delai minimum entre
# chaque appel plutot que d'attendre l'erreur 429 pour reagir.
# ---------------------------------------------------------------------------
_dernier_appel = {"t": 0.0}
_DELAI_MIN_ENTRE_APPELS = 3.5  # secondes, empirique pour rester sous 8000 TPM


def _throttle():
    """Espace les appels Groq pour eviter de taper le rate limit du plan gratuit."""
    ecoule = time.time() - _dernier_appel["t"]
    if ecoule < _DELAI_MIN_ENTRE_APPELS:
        time.sleep(_DELAI_MIN_ENTRE_APPELS - ecoule)
    _dernier_appel["t"] = time.time()


def _cle_panier(entreprise_id, session_id):
    return (entreprise_id, session_id)


def obtenir_panier(entreprise_id, session_id):
    return PANIERS.get(_cle_panier(entreprise_id, session_id), [])


def vider_panier(entreprise_id, session_id):
    PANIERS.pop(_cle_panier(entreprise_id, session_id), None)


def _appel_groq(messages, tools, max_tentatives=3):
    """Appelle Groq avec retry exponentiel sur les erreurs transitoires (rate limit, timeout, surcharge)."""
    derniere_erreur = None
    for tentative in range(1, max_tentatives + 1):
        try:
            _throttle()
            debut = time.time()
            response = client_groq.chat.completions.create(
                model=MODELE,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=400,
            )
            print(f"[moteur_ia] OK en {time.time() - debut:.1f}s (tentative {tentative})")
            return response
        except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as e:
            derniere_erreur = e
            attente = (2 ** tentative) + random.uniform(0, 1)
            print(f"[moteur_ia] Erreur transitoire ({type(e).__name__}) tentative {tentative}/{max_tentatives}, retry dans {attente:.1f}s")
            if tentative < max_tentatives:
                time.sleep(attente)
        except Exception as e:
            print(f"[moteur_ia] Erreur NON transitoire : {type(e).__name__} - {e}")
            raise
    raise derniere_erreur


def construire_prompt_systeme(entreprise, catalogue, creneaux, faq, client, dernier_rdv, derniere_commande):
    nom = entreprise["nom"]
    secteur = entreprise["secteur"]
    ton = entreprise["ton"] or "professionnel et chaleureux"
    description = entreprise["description"] or ""
    type_activite = entreprise["type_activite"]

    prompt = f"""Tu es l'assistant IA officiel de "{nom}" ({secteur}).

DESCRIPTION DE L'ENTREPRISE :
{description}

TON A ADOPTER : {ton}

REGLES GENERALES :
- Tu reponds toujours en francais, de maniere naturelle, comme sur WhatsApp (messages courts, pas de blabla inutile).
- Tu ne dis JAMAIS que tu es une IA generique : tu es l'assistant de {nom}, point.
- Tu utilises les outils (function calling) des que l'action correspond a une intention claire du client (ajouter au panier, valider une commande, prendre un rendez-vous, enregistrer ses coordonnees, enregistrer sa localisation).
- Tu ne factures/reserves jamais sans confirmation explicite du client.
- Si le client demande quelque chose hors du champ de l'entreprise, reste poli et recentre la conversation.
- IMPORTANT : Ne rappelle JAMAIS un outil de reservation, de commande ou de panier pour une action DEJA confirmee (voir "ETAT ACTUEL DE LA CONVERSATION" ci-dessous si present). Si le client donne juste son prenom, son telephone ou son anniversaire APRES une confirmation, utilise UNIQUEMENT enregistrer_client_info, rien d'autre.
- Si le message du client commence par ou contient "Localisation partagee" suivi de coordonnees, remercie-le brievement et utilise l'outil enregistrer_localisation avec les coordonnees exactes fournies dans le message. Precise que cela aide a mieux le situer (livraison, itineraire, etc.).
"""

    if client.get("prenom"):
        prompt += f"\nLe client s'appelle {client['prenom']}. Utilise son prenom naturellement de temps en temps.\n"
    else:
        prompt += "\nTu ne connais pas encore le prenom du client : demande-le poliment tot dans la conversation (juste apres l'avoir salue), en une phrase courte et naturelle, sans en faire un interrogatoire.\n"

    if client.get("telephone"):
        prompt += f"\nLe client a deja fourni son telephone ({client['telephone']}). Ne le redemande pas.\n"
    else:
        prompt += "\nTu ne connais pas encore le numero de telephone du client : demande-le a un moment naturel de la conversation (par exemple juste avant de valider une commande ou un rendez-vous, en expliquant que c'est pour le recontacter ou confirmer), sans etre insistant si le sujet principal n'est pas encore traite.\n"

    if client.get("date_anniversaire"):
        prompt += f"\nDate d'anniversaire du client deja connue : {client['date_anniversaire']}.\n"
    else:
        prompt += "\nTu ne connais pas encore la date d'anniversaire du client : tu peux la lui demander une seule fois au cours de la conversation, avec tact (par exemple en expliquant que cela permet de lui faire une surprise ou une offre le jour J). N'insiste jamais s'il ne repond pas ou change de sujet, et ne la redemande plus ensuite dans la meme conversation.\n"

    if client.get("latitude") and client.get("longitude"):
        prompt += f"\nLe client a deja partage sa position ({client['latitude']}, {client['longitude']}). Tu peux t'y referer si utile, sans avoir besoin de la redemander.\n"

    if dernier_rdv:
        prompt += f"\nETAT ACTUEL DE LA CONVERSATION : le client a DEJA un rendez-vous confirme : {dernier_rdv['libelle']} le {dernier_rdv['jour']} a {dernier_rdv['heure']}. Ne reserve PAS un nouveau creneau sauf si le client le demande explicitement et clairement (ex: 'je veux un autre rendez-vous').\n"

    if derniere_commande:
        moyen = f" (paye via {derniere_commande['moyen_paiement']})" if derniere_commande.get("moyen_paiement") else ""
        prompt += f"\nETAT ACTUEL DE LA CONVERSATION : le client a DEJA une commande validee (total {int(derniere_commande['total'])} FCFA{moyen}). Ne revalide pas une commande deja validee sauf nouvelle commande explicitement demandee.\n"

    if faq:
        prompt += "\nQUESTIONS FREQUENTES (utilise ces reponses si le client pose une question similaire) :\n"
        for f in faq:
            prompt += f"- Q: {f['question']}\n  R: {f['reponse']}\n"

    if type_activite == "commande":
        prompt += "\nCATALOGUE DISPONIBLE :\n"
        categorie_actuelle = None
        for item in catalogue:
            if item["categorie"] != categorie_actuelle:
                categorie_actuelle = item["categorie"]
                prompt += f"\n{categorie_actuelle} :\n"
            prompt += f"- {item['nom']} : {int(item['prix'])} {item['devise']} - {item['description']}\n"
        prompt += f"""
MOYENS DE PAIEMENT ACCEPTES : {', '.join(MOYENS_PAIEMENT)}.

PROCESSUS DE COMMANDE :
1. Aide le client a choisir des articles du catalogue ci-dessus.
2. Utilise l'outil ajouter_au_panier a chaque fois que le client confirme vouloir un article (tu peux l'appeler plusieurs fois dans le meme tour si le client demande plusieurs choses a la fois).
3. Si le client change d'avis sur un article, utilise retirer_du_panier ou modifier_quantite_panier selon le cas.
4. Si le client veut tout annuler avant validation, utilise annuler_commande.
5. Tu peux proposer un article complementaire (upsell) une seule fois, avec tact.
6. Quand le client dit qu'il a termine, utilise voir_panier pour recapituler AVANT de valider.
7. Demande ensuite son moyen de paiement parmi la liste ci-dessus (n'invente pas d'autres moyens).
8. Valide la commande avec valider_commande UNIQUEMENT apres confirmation explicite du client sur le recapitulatif ET apres avoir obtenu le moyen de paiement. Passe le moyen de paiement choisi en argument.
9. AVANT de valider la commande, tu DOIS t'assurer que le client a partage sa position en temps reel
   (bouton de localisation dans l'interface). S'il ne l'a pas encore fait, demande-le clairement et
   attends sa localisation avant d'appeler valider_commande — l'outil refusera sinon.
"""
    elif type_activite == "rendez_vous":
        prompt += "\nCRENEAUX DISPONIBLES :\n"
        for c in creneaux:
            prompt += f"- [id:{c['id']}] {c['libelle']} - {c['jour']} a {c['heure']}\n"
        prompt += """
PROCESSUS DE PRISE DE RENDEZ-VOUS (sois tres clair et structure a chaque etape) :
1. Comprends quel type de consultation/service interesse le client ; si ce n'est pas precise, demande-le clairement.
2. Propose 2 a 4 creneaux disponibles correspondants (liste ci-dessus), formules simplement : jour + heure.
3. Quand le client choisit un creneau precis, confirme d'abord en une phrase courte ("Vous voulez donc [service] le [jour] a [heure], c'est bien ca ?") avant de reserver, sauf si son message est deja totalement explicite.
4. Utilise l'outil prendre_rendez_vous avec l'id du creneau choisi.
5. Apres reservation, confirme clairement avec le jour, l'heure et un rappel de ce qu'il faut apporter si l'info est disponible dans les FAQ.
6. Une fois le rendez-vous confirme, N'appelle plus prendre_rendez_vous dans cette conversation sauf nouvelle demande explicite.
"""
    else:
        prompt += """
Tu n'as pas de catalogue ni d'agenda predefini pour cette entreprise (secteur personnalise).
Concentre-toi sur : comprendre le besoin du client, repondre avec les FAQ disponibles,
et si tu ne peux pas repondre, propose de collecter ses coordonnees pour qu'un conseiller le recontacte.
"""

    prompt += """
Si le client donne son prenom, son numero, ou sa date d'anniversaire au cours de la conversation
(que ce soit spontanement ou en reponse a ta question), utilise l'outil enregistrer_client_info
pour le memoriser, meme si ce n'est pas le sujet principal.
Cet outil est INDEPENDANT des outils de commande/rendez-vous : ne declenche jamais une reservation
ou une commande juste parce que le client donne une information personnelle.
"""

    return prompt


def obtenir_tools(type_activite):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "enregistrer_client_info",
                "description": "Enregistre les informations personnelles du client mentionnees dans la conversation (prenom, telephone, date d'anniversaire). Appelle cette fonction des qu'une info est donnee. N'a aucun rapport avec les reservations ou commandes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prenom": {"type": "string", "description": "Prenom du client"},
                        "telephone": {"type": "string", "description": "Numero de telephone du client"},
                        "date_anniversaire": {"type": "string", "description": "Date d'anniversaire, format libre (ex: 12 mars)"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "enregistrer_localisation",
                "description": "Enregistre la position GPS partagee par le client (latitude/longitude). A utiliser quand le message du client contient une localisation partagee.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number", "description": "Latitude GPS"},
                        "longitude": {"type": "number", "description": "Longitude GPS"},
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        },
    ]

    if type_activite == "commande":
        tools += [
            {
                "type": "function",
                "function": {
                    "name": "ajouter_au_panier",
                    "description": "Ajoute un article du catalogue au panier du client.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nom_item": {"type": "string", "description": "Nom exact de l'article dans le catalogue"},
                            "quantite": {"type": "integer", "description": "Quantite souhaitee", "default": 1},
                        },
                        "required": ["nom_item"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "retirer_du_panier",
                    "description": "Retire completement un article du panier (le client ne le veut plus).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nom_item": {"type": "string", "description": "Nom exact ou approximatif de l'article a retirer"},
                        },
                        "required": ["nom_item"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "modifier_quantite_panier",
                    "description": "Change la quantite d'un article deja present dans le panier.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nom_item": {"type": "string"},
                            "quantite": {"type": "integer", "description": "Nouvelle quantite. Si 0, l'article est retire."},
                        },
                        "required": ["nom_item", "quantite"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "annuler_commande",
                    "description": "Vide entierement le panier (le client annule tout, avant validation).",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "voir_panier",
                    "description": "Recupere le contenu actuel du panier et le total, pour le recapituler au client.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "valider_commande",
                    "description": "Valide definitivement la commande apres confirmation explicite du client ET apres avoir obtenu son moyen de paiement. A utiliser une seule fois par commande.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "moyen_paiement": {
                                "type": "string",
                                "description": "Moyen de paiement choisi par le client",
                                "enum": MOYENS_PAIEMENT,
                            },
                        },
                        "required": ["moyen_paiement"],
                    },
                },
            },
        ]
    elif type_activite == "rendez_vous":
        tools += [
            {
                "type": "function",
                "function": {
                    "name": "prendre_rendez_vous",
                    "description": "Reserve un creneau precis pour le client. Ne pas appeler si un rendez-vous est deja confirme dans cette conversation, sauf nouvelle demande explicite du client.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "creneau_id": {"type": "integer", "description": "L'id du creneau choisi (indique entre crochets dans la liste des creneaux)"},
                        },
                        "required": ["creneau_id"],
                    },
                },
            },
        ]

    return tools


def executer_outil(nom_fonction, arguments, entreprise_id, session_id):
    if nom_fonction == "enregistrer_client_info":
        database.maj_client(
            session_id, entreprise_id,
            prenom=arguments.get("prenom"),
            telephone=arguments.get("telephone"),
            date_anniversaire=arguments.get("date_anniversaire"),
        )
        return {"statut": "ok", "message": "Informations enregistrees.", "evenement": "client_maj"}

    if nom_fonction == "enregistrer_localisation":
        latitude = arguments.get("latitude")
        longitude = arguments.get("longitude")
        database.maj_client(session_id, entreprise_id, latitude=latitude, longitude=longitude)
        return {
            "statut": "ok", "message": "Position enregistree.",
            "latitude": latitude, "longitude": longitude,
            "evenement": "localisation_enregistree",
        }

    if nom_fonction == "ajouter_au_panier":
        catalogue = database.obtenir_catalogue(entreprise_id)
        nom_recherche = arguments.get("nom_item", "").strip().lower()
        item_trouve = None
        for item in catalogue:
            if item["nom"].strip().lower() == nom_recherche or nom_recherche in item["nom"].strip().lower():
                item_trouve = item
                break
        if not item_trouve:
            return {"statut": "erreur", "message": f"Article '{arguments.get('nom_item')}' introuvable dans le catalogue."}

        quantite = arguments.get("quantite", 1)
        cle = _cle_panier(entreprise_id, session_id)
        panier = PANIERS.setdefault(cle, [])

        ligne_existante = next((i for i in panier if i["nom"] == item_trouve["nom"]), None)
        if ligne_existante:
            ligne_existante["quantite"] += quantite
        else:
            panier.append({
                "nom": item_trouve["nom"],
                "prix": item_trouve["prix"],
                "quantite": quantite,
            })
        return {"statut": "ok", "item_ajoute": item_trouve["nom"], "quantite": quantite}

    if nom_fonction == "retirer_du_panier":
        cle = _cle_panier(entreprise_id, session_id)
        panier = PANIERS.get(cle, [])
        nom_recherche = arguments.get("nom_item", "").strip().lower()
        avant = len(panier)
        panier = [i for i in panier if nom_recherche not in i["nom"].strip().lower()]
        PANIERS[cle] = panier
        if len(panier) == avant:
            return {"statut": "erreur", "message": f"'{arguments.get('nom_item')}' n'est pas dans le panier."}
        return {"statut": "ok", "item_retire": arguments.get("nom_item")}

    if nom_fonction == "modifier_quantite_panier":
        cle = _cle_panier(entreprise_id, session_id)
        panier = PANIERS.get(cle, [])
        nom_recherche = arguments.get("nom_item", "").strip().lower()
        quantite = arguments.get("quantite", 1)
        trouve = False
        nouveau_panier = []
        for i in panier:
            if nom_recherche in i["nom"].strip().lower():
                trouve = True
                if quantite > 0:
                    i["quantite"] = quantite
                    nouveau_panier.append(i)
            else:
                nouveau_panier.append(i)
        PANIERS[cle] = nouveau_panier
        if not trouve:
            return {"statut": "erreur", "message": f"'{arguments.get('nom_item')}' n'est pas dans le panier."}
        return {"statut": "ok", "item": arguments.get("nom_item"), "nouvelle_quantite": quantite}

    if nom_fonction == "annuler_commande":
        vider_panier(entreprise_id, session_id)
        return {"statut": "ok", "message": "Panier vide."}

    if nom_fonction == "voir_panier":
        panier = obtenir_panier(entreprise_id, session_id)
        total = sum(i["prix"] * i["quantite"] for i in panier)
        return {"panier": panier, "total": total}

    if nom_fonction == "valider_commande":
        panier = obtenir_panier(entreprise_id, session_id)
        if not panier:
            return {"statut": "erreur", "message": "Le panier est vide."}

        client = database.obtenir_ou_creer_client(entreprise_id, session_id)
        if not client.get("latitude") or not client.get("longitude"):
            return {
                "statut": "erreur",
                "message": "Le client doit d'abord partager sa position (bouton de localisation) avant de valider la commande.",
            }

        total = sum(i["prix"] * i["quantite"] for i in panier)
        moyen_paiement = arguments.get("moyen_paiement") or "Non precise"
        commande_id = database.creer_commande(entreprise_id, session_id, panier, total, moyen_paiement)
        vider_panier(entreprise_id, session_id)
        return {
            "statut": "ok", "commande_id": commande_id, "total": total,
            "moyen_paiement": moyen_paiement, "evenement": "commande_creee",
        }

    if nom_fonction == "prendre_rendez_vous":
        creneau_id = arguments.get("creneau_id")
        creneaux = database.obtenir_creneaux_disponibles(entreprise_id)
        creneau = next((c for c in creneaux if c["id"] == creneau_id), None)
        if not creneau:
            return {"statut": "erreur", "message": "Ce creneau n'est plus disponible."}
        rdv_id = database.creer_rendez_vous(entreprise_id, session_id, creneau_id)
        return {
            "statut": "ok", "rdv_id": rdv_id,
            "libelle": creneau["libelle"], "jour": creneau["jour"], "heure": creneau["heure"],
            "evenement": "rdv_cree",
        }

    return {"statut": "erreur", "message": f"Fonction inconnue : {nom_fonction}"}


OUTILS_QUI_TOUCHENT_LE_PANIER = {
    "ajouter_au_panier", "retirer_du_panier", "modifier_quantite_panier",
    "annuler_commande", "valider_commande",
}

OUTILS_QUI_TOUCHENT_LE_CLIENT = {"enregistrer_client_info", "enregistrer_localisation"}


def traiter_message(entreprise_id, session_id, message_utilisateur, on_panier_modifie=None, on_client_modifie=None):
    entreprise = database.obtenir_entreprise(entreprise_id)
    if not entreprise:
        return {"reponse": "Configuration introuvable.", "evenements": []}

    catalogue = database.obtenir_catalogue(entreprise_id) if entreprise["type_activite"] == "commande" else []
    creneaux = database.obtenir_creneaux_disponibles(entreprise_id) if entreprise["type_activite"] == "rendez_vous" else []
    faq = database.obtenir_faq(entreprise_id)
    client = database.obtenir_ou_creer_client(entreprise_id, session_id)
    dernier_rdv = database.obtenir_dernier_rdv(entreprise_id, session_id) if entreprise["type_activite"] == "rendez_vous" else None
    derniere_commande = database.obtenir_derniere_commande(entreprise_id, session_id) if entreprise["type_activite"] == "commande" else None

    prompt_systeme = construire_prompt_systeme(entreprise, catalogue, creneaux, faq, client, dernier_rdv, derniere_commande)

    # Historique reduit a 6 messages (au lieu de 16) pour limiter la
    # consommation de tokens a chaque appel et rester sous le rate limit.
    historique = database.obtenir_historique(entreprise_id, session_id, limite=6)

    messages = [{"role": "system", "content": prompt_systeme}]
    for h in historique:
        messages.append({"role": h["role"], "content": h["contenu"]})
    messages.append({"role": "user", "content": message_utilisateur})

    database.ajouter_message(entreprise_id, session_id, "user", message_utilisateur)

    tools = obtenir_tools(entreprise["type_activite"])
    evenements = []

    try:
        response = _appel_groq(messages, tools)
        message_ia = response.choices[0].message

        boucles = 0
        while message_ia.tool_calls and boucles < 5:
            boucles += 1
            messages.append({
                "role": "assistant",
                "content": message_ia.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message_ia.tool_calls
                ],
            })

            for tool_call in message_ia.tool_calls:
                nom_fonction = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                print(f"[moteur_ia] Execution outil : {nom_fonction}({arguments})")
                resultat = executer_outil(nom_fonction, arguments, entreprise_id, session_id)

                if resultat.get("evenement"):
                    evenements.append({"type": resultat["evenement"], "details": resultat})

                if nom_fonction in OUTILS_QUI_TOUCHENT_LE_PANIER and on_panier_modifie:
                    on_panier_modifie()

                if nom_fonction in OUTILS_QUI_TOUCHENT_LE_CLIENT and on_client_modifie:
                    on_client_modifie()

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(resultat),
                })

            response = _appel_groq(messages, tools)
            message_ia = response.choices[0].message

        texte_final = message_ia.content or "Desole, je n'ai pas pu traiter votre demande."
        database.ajouter_message(entreprise_id, session_id, "assistant", texte_final)

        return {"reponse": texte_final, "evenements": evenements}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[moteur_ia] ERREUR FINALE : {type(e).__name__} - {e}")
        return {
            "reponse": "Une petite lenteur de notre cote, reessayez dans quelques secondes 🙏",
            "evenements": [],
        }