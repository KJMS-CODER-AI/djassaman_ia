import os
import uuid
import urllib.parse
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

import database
import moteur_ia

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "djassaman_ia_secret")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

database.init_db()

# Peuple automatiquement la base avec les demos si elle est vide.
# Utile en production (Render) ou le disque est ephemere et se
# reinitialise a chaque redemarrage/redeploiement.
if not database.lister_entreprises():
    import seed_demos
    seed_demos.seed()


def _room_admin(entreprise_id):
    return f"admin_{entreprise_id}"


def _generer_lien_whatsapp_livreur(commande):
    """Construit un lien wa.me pre-rempli avec le recap de la commande, pour que
    l'admin puisse transferer en un clic au livreur (sans avoir a tout retaper)."""
    lignes = [f"Nouvelle commande #{commande['id']}"]
    for item in commande.get("items", []):
        lignes.append(f"- {item['quantite']} x {item['nom']}")
    lignes.append(f"Total : {int(commande['total'])} FCFA")
    if commande.get("moyen_paiement"):
        lignes.append(f"Paiement : {commande['moyen_paiement']}")
    if commande.get("prenom"):
        lignes.append(f"Client : {commande['prenom']}")
    if commande.get("telephone"):
        lignes.append(f"Tel : {commande['telephone']}")
    if commande.get("latitude") and commande.get("longitude"):
        lien_maps = f"https://www.google.com/maps?q={commande['latitude']},{commande['longitude']}"
        lignes.append(f"Position : {lien_maps}")

    texte = "\n".join(lignes)
    return "https://wa.me/?text=" + urllib.parse.quote(texte)


@app.route("/")
def accueil():
    return render_template("dashboard.html")


@app.route("/demo")
def demo_simple():
    return render_template("demo.html")


@app.route("/api/entreprises")
def api_entreprises():
    entreprises = database.lister_entreprises()
    details = []
    for e in entreprises:
        complet = database.obtenir_entreprise(e["id"])
        details.append({
            "id": complet["id"],
            "nom": complet["nom"],
            "secteur": complet["secteur"],
            "type_activite": complet["type_activite"],
            "message_accueil": complet["message_accueil"],
            "couleur_primaire": complet["couleur_primaire"],
        })
    return jsonify(details)


@app.route("/api/stats/<entreprise_id>")
def api_stats(entreprise_id):
    commandes = database.compter_commandes(entreprise_id)
    rdv = database.compter_rendez_vous(entreprise_id)
    conversations = database.compter_conversations(entreprise_id)
    return jsonify({
        "conversations": conversations,
        "commandes": commandes["nombre"],
        "chiffre_affaires": commandes["total"],
        "rendez_vous": rdv,
    })


@app.route("/api/stats-graph/<entreprise_id>")
def api_stats_graph(entreprise_id):
    return jsonify(database.obtenir_stats_journalieres(entreprise_id, jours=7))


@app.route("/api/top-produits/<entreprise_id>")
def api_top_produits(entreprise_id):
    return jsonify(database.obtenir_top_produits(entreprise_id, limite=6))


@app.route("/api/clients/<entreprise_id>")
def api_clients(entreprise_id):
    return jsonify(database.obtenir_clients_entreprise(entreprise_id))


@app.route("/api/prochain-rdv/<entreprise_id>/<session_id>")
def api_prochain_rdv(entreprise_id, session_id):
    rdv = database.obtenir_dernier_rdv(entreprise_id, session_id)
    return jsonify(rdv or {})


@app.route("/api/historique/<entreprise_id>/<session_id>")
def api_historique(entreprise_id, session_id):
    """Retourne l'historique adapte au secteur : commandes passees, ou rendez-vous passes."""
    entreprise = database.obtenir_entreprise(entreprise_id)
    if entreprise and entreprise["type_activite"] == "rendez_vous":
        return jsonify({
            "type": "rendez_vous",
            "items": database.obtenir_historique_rdv(entreprise_id, session_id),
        })
    return jsonify({
        "type": "commande",
        "items": database.obtenir_historique_commandes(entreprise_id, session_id),
    })


@app.route("/api/note/<entreprise_id>/<session_id>", methods=["GET"])
def api_get_note(entreprise_id, session_id):
    return jsonify({"contenu": database.obtenir_note(entreprise_id, session_id)})


@app.route("/api/note/<entreprise_id>/<session_id>", methods=["POST"])
def api_set_note(entreprise_id, session_id):
    contenu = (request.json or {}).get("contenu", "")
    database.sauvegarder_note(entreprise_id, session_id, contenu)
    return jsonify({"statut": "ok"})


@app.route("/api/nouvelle-session")
def api_nouvelle_session():
    return jsonify({"session_id": uuid.uuid4().hex})


# ---------- PRODUITS / MENU (dashboard admin) ----------

@app.route("/api/produits/<entreprise_id>")
def api_produits(entreprise_id):
    """Liste TOUS les produits (disponibles ou non) pour la page de gestion."""
    return jsonify(database.obtenir_catalogue_admin(entreprise_id))


@app.route("/api/produits/<entreprise_id>", methods=["POST"])
def api_produit_creer(entreprise_id):
    data = request.json or {}
    nom = (data.get("nom") or "").strip()
    if not nom:
        return jsonify({"erreur": "Le nom du produit est requis"}), 400
    try:
        prix = float(data.get("prix") or 0)
    except (TypeError, ValueError):
        prix = 0
    item_id = database.ajouter_item_catalogue(
        entreprise_id,
        nom,
        (data.get("description") or "").strip(),
        (data.get("categorie") or "Autre").strip(),
        prix,
        data.get("devise") or "FCFA",
    )
    return jsonify({"statut": "ok", "id": item_id})


@app.route("/api/produits/item/<int:item_id>", methods=["POST"])
def api_produit_modifier(item_id):
    data = request.json or {}
    prix = data.get("prix")
    try:
        prix = float(prix) if prix is not None else None
    except (TypeError, ValueError):
        prix = None
    database.modifier_item_catalogue(
        item_id,
        nom=data.get("nom"),
        description=data.get("description"),
        categorie=data.get("categorie"),
        prix=prix,
        devise=data.get("devise"),
    )
    return jsonify({"statut": "ok"})


@app.route("/api/produits/item/<int:item_id>/disponibilite", methods=["POST"])
def api_produit_disponibilite(item_id):
    disponible = (request.json or {}).get("disponible", True)
    database.changer_disponibilite_item(item_id, disponible)
    return jsonify({"statut": "ok"})


@app.route("/api/produits/item/<int:item_id>", methods=["DELETE"])
def api_produit_supprimer(item_id):
    database.supprimer_item_catalogue(item_id)
    return jsonify({"statut": "ok"})


# ---------- COMMANDES (dashboard admin) ----------

@app.route("/api/commandes/<entreprise_id>")
def api_commandes(entreprise_id):
    statut = request.args.get("statut")
    return jsonify(database.obtenir_commandes_entreprise(entreprise_id, statut=statut))


@app.route("/api/commandes/<int:commande_id>", methods=["GET"])
def api_commande_detail(commande_id):
    commande = database.obtenir_commande(commande_id)
    if not commande:
        return jsonify({"erreur": "Commande introuvable"}), 404
    return jsonify(commande)


@app.route("/api/commandes/<int:commande_id>/statut", methods=["POST"])
def api_commande_statut(commande_id):
    statut = (request.json or {}).get("statut")
    if statut not in ("nouvelle", "en_preparation", "en_livraison", "livree", "annulee"):
        return jsonify({"erreur": "Statut invalide"}), 400
    database.changer_statut_commande(commande_id, statut)
    commande = database.obtenir_commande(commande_id)
    if commande:
        socketio.emit(
            "commande_statut_maj",
            {"commande_id": commande_id, "statut": statut},
            room=_room_admin(commande["entreprise_id"]),
        )
    return jsonify({"statut": "ok"})


@app.route("/api/commandes/<int:commande_id>/vue", methods=["POST"])
def api_commande_vue(commande_id):
    database.marquer_commande_vue(commande_id)
    return jsonify({"statut": "ok"})


@app.route("/api/commandes/<int:commande_id>/lien-livreur")
def api_commande_lien_livreur(commande_id):
    commande = database.obtenir_commande(commande_id)
    if not commande:
        return jsonify({"erreur": "Commande introuvable"}), 404
    lien = _generer_lien_whatsapp_livreur(commande)
    return jsonify({"lien_whatsapp": lien})


# ---------- RENDEZ-VOUS (dashboard admin) ----------

@app.route("/api/rendez-vous/<entreprise_id>")
def api_rendez_vous(entreprise_id):
    return jsonify(database.obtenir_rendez_vous_entreprise(entreprise_id))


@app.route("/api/rendez-vous/<int:rdv_id>/vue", methods=["POST"])
def api_rdv_vue(rdv_id):
    database.marquer_rdv_vue(rdv_id)
    return jsonify({"statut": "ok"})


# ---------- NOTIFICATIONS (badges du menu) ----------

@app.route("/api/notifications/<entreprise_id>")
def api_notifications(entreprise_id):
    return jsonify({
        "commandes_non_vues": database.compter_commandes_non_vues(entreprise_id),
        "rdv_non_vus": database.compter_rdv_non_vus(entreprise_id),
    })


@app.route("/api/notifications/<entreprise_id>/tout-marquer-vu", methods=["POST"])
def api_notifications_tout_marquer_vu(entreprise_id):
    cible = (request.json or {}).get("type")
    if cible == "commandes":
        database.marquer_toutes_commandes_vues(entreprise_id)
    elif cible == "rendez_vous":
        database.marquer_tous_rdv_vus(entreprise_id)
    return jsonify({"statut": "ok"})


@socketio.on("connect")
def on_connect():
    print("[socket] Client connecte")


@socketio.on("disconnect")
def on_disconnect():
    print("[socket] Client deconnecte")


@socketio.on("rejoindre_admin")
def on_rejoindre_admin(data):
    """Le dashboard admin appelle cet event a l'ouverture pour recevoir les notifications en temps reel."""
    entreprise_id = data.get("entreprise_id")
    if not entreprise_id:
        return
    join_room(_room_admin(entreprise_id))
    print(f"[socket] Admin rejoint la room {_room_admin(entreprise_id)}")


@socketio.on("envoyer_message")
def on_envoyer_message(data):
    entreprise_id = data.get("entreprise_id")
    session_id = data.get("session_id")
    message_utilisateur = (data.get("message") or "").strip()

    if not entreprise_id or not session_id or not message_utilisateur:
        emit("erreur", {"message": "Donnees invalides."})
        return

    emit("en_train_decrire", {})

    def emettre_panier():
        panier = moteur_ia.obtenir_panier(entreprise_id, session_id)
        total = sum(i["prix"] * i["quantite"] for i in panier)
        socketio.emit("panier_maj", {"panier": panier, "total": total}, room=session_id)

    def emettre_client():
        client = database.obtenir_ou_creer_client(entreprise_id, session_id)
        socketio.emit("client_maj", {"client": client}, room=session_id)

    resultat = moteur_ia.traiter_message(
        entreprise_id, session_id, message_utilisateur,
        on_panier_modifie=emettre_panier, on_client_modifie=emettre_client,
    )

    emit("nouvelle_reponse", {
        "reponse": resultat["reponse"],
        "evenements": resultat["evenements"],
    })

    emettre_panier()
    emettre_client()

    for ev in resultat["evenements"]:
        if ev["type"] == "commande_creee":
            commande_id = ev["details"].get("commande_id")
            commande = database.obtenir_commande(commande_id) if commande_id else None
            if commande:
                socketio.emit(
                    "nouvelle_commande",
                    {
                        "commande": commande,
                        "lien_whatsapp": _generer_lien_whatsapp_livreur(commande),
                    },
                    room=_room_admin(entreprise_id),
                )

        if ev["type"] == "rdv_cree":
            rdv = database.obtenir_dernier_rdv(entreprise_id, session_id)
            socketio.emit(
                "nouveau_rdv",
                {"rdv": rdv},
                room=_room_admin(entreprise_id),
            )
            emit("rdv_maj", {"rdv": rdv})


@socketio.on("demarrer_conversation")
def on_demarrer_conversation(data):
    entreprise_id = data.get("entreprise_id")
    session_id = data.get("session_id")

    entreprise = database.obtenir_entreprise(entreprise_id)
    if not entreprise:
        emit("erreur", {"message": "Secteur introuvable."})
        return

    join_room(session_id)

    client = database.obtenir_ou_creer_client(entreprise_id, session_id)
    historique = database.obtenir_historique(entreprise_id, session_id, limite=50)
    panier = moteur_ia.obtenir_panier(entreprise_id, session_id)
    total = sum(i["prix"] * i["quantite"] for i in panier)
    dernier_rdv = database.obtenir_dernier_rdv(entreprise_id, session_id) if entreprise["type_activite"] == "rendez_vous" else None

    emit("conversation_initialisee", {
        "message_accueil": entreprise["message_accueil"],
        "historique": historique,
        "client": client,
        "panier": panier,
        "total": total,
        "dernier_rdv": dernier_rdv,
        "type_activite": entreprise["type_activite"],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)