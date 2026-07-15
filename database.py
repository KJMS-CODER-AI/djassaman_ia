import sqlite3
import json
import os
import re
from datetime import datetime, timedelta

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "djassaman_ia.db"),
)

MOIS_FR = {
    "janvier": 1, "fevrier": 2, "fÃ©vrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "aoÃ»t": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "dÃ©cembre": 12,
}


def parser_date_anniversaire(texte):
    """Extrait (jour, mois) d'une date libre : '12/03', '12 mars', etc. Retourne None si non reconnu."""
    if not texte:
        return None
    texte = texte.strip().lower()

    m = re.match(r"^(\d{1,2})[\/\-](\d{1,2})", texte)
    if m:
        jour, mois = int(m.group(1)), int(m.group(2))
        if 1 <= jour <= 31 and 1 <= mois <= 12:
            return (jour, mois)

    m2 = re.match(r"^(\d{1,2})\s+([a-zÃ©Ã»]+)", texte)
    if m2:
        jour = int(m2.group(1))
        mois = MOIS_FR.get(m2.group(2))
        if mois:
            return (jour, mois)

    return None


def est_anniversaire_aujourdhui(date_anniversaire):
    parsed = parser_date_anniversaire(date_anniversaire)
    if not parsed:
        return False
    jour, mois = parsed
    aujourdhui = datetime.utcnow()
    return jour == aujourdhui.day and mois == aujourdhui.month


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS entreprises (
            id TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            secteur TEXT NOT NULL,
            type_activite TEXT NOT NULL,
            ton TEXT,
            description TEXT,
            message_accueil TEXT,
            couleur_primaire TEXT DEFAULT '#25D366',
            actif INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogue_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            nom TEXT NOT NULL,
            description TEXT,
            categorie TEXT,
            prix REAL,
            devise TEXT DEFAULT 'FCFA',
            disponible INTEGER DEFAULT 1,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS creneaux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            libelle TEXT NOT NULL,
            jour TEXT NOT NULL,
            heure TEXT NOT NULL,
            disponible INTEGER DEFAULT 1,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS faq_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            question TEXT NOT NULL,
            reponse TEXT NOT NULL,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            prenom TEXT,
            telephone TEXT,
            date_anniversaire TEXT,
            latitude REAL,
            longitude REAL,
            date_creation TEXT NOT NULL,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            contenu TEXT NOT NULL,
            date_creation TEXT NOT NULL,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            items_json TEXT NOT NULL,
            total REAL NOT NULL,
            moyen_paiement TEXT,
            statut TEXT DEFAULT 'nouvelle',
            date_creation TEXT NOT NULL,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rendez_vous (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            creneau_id INTEGER NOT NULL,
            statut TEXT DEFAULT 'confirme',
            date_creation TEXT NOT NULL,
            FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
            FOREIGN KEY (creneau_id) REFERENCES creneaux(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes_client (
            entreprise_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            contenu TEXT,
            date_maj TEXT,
            PRIMARY KEY (entreprise_id, session_id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_catalogue_entreprise ON catalogue_items(entreprise_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_creneaux_entreprise ON creneaux(entreprise_id)")

    conn.commit()
    conn.close()

    _migrer_colonnes_manquantes()


def _migrer_colonnes_manquantes():
    """Ajoute les colonnes recentes sur les bases existantes creees avant cette mise a jour."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(clients)")
    colonnes_clients = [r[1] for r in cur.fetchall()]
    if "latitude" not in colonnes_clients:
        cur.execute("ALTER TABLE clients ADD COLUMN latitude REAL")
    if "longitude" not in colonnes_clients:
        cur.execute("ALTER TABLE clients ADD COLUMN longitude REAL")

    cur.execute("PRAGMA table_info(commandes)")
    colonnes_commandes = [r[1] for r in cur.fetchall()]
    if "moyen_paiement" not in colonnes_commandes:
        cur.execute("ALTER TABLE commandes ADD COLUMN moyen_paiement TEXT")
    if "vue" not in colonnes_commandes:
        cur.execute("ALTER TABLE commandes ADD COLUMN vue INTEGER DEFAULT 0")

    cur.execute("PRAGMA table_info(rendez_vous)")
    colonnes_rdv = [r[1] for r in cur.fetchall()]
    if "vue" not in colonnes_rdv:
        cur.execute("ALTER TABLE rendez_vous ADD COLUMN vue INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def init_notes_table():
    # Conserve pour compatibilite : la table est deja creee dans init_db()
    pass


def obtenir_entreprise(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM entreprises WHERE id = ?", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def lister_entreprises():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nom, secteur, type_activite FROM entreprises WHERE actif = 1")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def creer_ou_maj_entreprise(id, nom, secteur, type_activite, ton, description, message_accueil, couleur_primaire="#25D366"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entreprises (id, nom, secteur, type_activite, ton, description, message_accueil, couleur_primaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nom=excluded.nom, secteur=excluded.secteur, type_activite=excluded.type_activite,
            ton=excluded.ton, description=excluded.description,
            message_accueil=excluded.message_accueil, couleur_primaire=excluded.couleur_primaire
    """, (id, nom, secteur, type_activite, ton, description, message_accueil, couleur_primaire))
    conn.commit()
    conn.close()


def ajouter_item_catalogue(entreprise_id, nom, description, categorie, prix, devise="FCFA"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO catalogue_items (entreprise_id, nom, description, categorie, prix, devise)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entreprise_id, nom, description, categorie, prix, devise))
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def obtenir_catalogue(entreprise_id):
    """Retourne uniquement les articles disponibles (utilise par le moteur IA pour le catalogue propose au client)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM catalogue_items
        WHERE entreprise_id = ? AND disponible = 1
        ORDER BY categorie, nom
    """, (entreprise_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtenir_catalogue_admin(entreprise_id):
    """Retourne TOUS les articles (disponibles ou non), pour la page de gestion Produits/Menu."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM catalogue_items
        WHERE entreprise_id = ?
        ORDER BY categorie, nom
    """, (entreprise_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtenir_item_catalogue(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM catalogue_items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def modifier_item_catalogue(item_id, nom=None, description=None, categorie=None, prix=None, devise=None):
    conn = get_connection()
    cur = conn.cursor()
    champs = []
    valeurs = []
    if nom is not None:
        champs.append("nom = ?")
        valeurs.append(nom)
    if description is not None:
        champs.append("description = ?")
        valeurs.append(description)
    if categorie is not None:
        champs.append("categorie = ?")
        valeurs.append(categorie)
    if prix is not None:
        champs.append("prix = ?")
        valeurs.append(prix)
    if devise is not None:
        champs.append("devise = ?")
        valeurs.append(devise)
    if champs:
        valeurs.append(item_id)
        cur.execute(f"UPDATE catalogue_items SET {', '.join(champs)} WHERE id = ?", valeurs)
        conn.commit()
    conn.close()


def changer_disponibilite_item(item_id, disponible):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE catalogue_items SET disponible = ? WHERE id = ?", (1 if disponible else 0, item_id))
    conn.commit()
    conn.close()


def supprimer_item_catalogue(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM catalogue_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def ajouter_creneau(entreprise_id, libelle, jour, heure):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO creneaux (entreprise_id, libelle, jour, heure)
        VALUES (?, ?, ?, ?)
    """, (entreprise_id, libelle, jour, heure))
    conn.commit()
    conn.close()


def obtenir_creneaux_disponibles(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM creneaux
        WHERE entreprise_id = ? AND disponible = 1
        ORDER BY jour, heure
    """, (entreprise_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reserver_creneau(creneau_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE creneaux SET disponible = 0 WHERE id = ?", (creneau_id,))
    conn.commit()
    conn.close()


def ajouter_faq(entreprise_id, question, reponse):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO faq_items (entreprise_id, question, reponse)
        VALUES (?, ?, ?)
    """, (entreprise_id, question, reponse))
    conn.commit()
    conn.close()


def obtenir_faq(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT question, reponse FROM faq_items WHERE entreprise_id = ?", (entreprise_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtenir_ou_creer_client(entreprise_id, session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE entreprise_id = ? AND session_id = ?", (entreprise_id, session_id))
    row = cur.fetchone()
    if row:
        conn.close()
        return dict(row)

    cur.execute("""
        INSERT INTO clients (entreprise_id, session_id, date_creation)
        VALUES (?, ?, ?)
    """, (entreprise_id, session_id, datetime.utcnow().isoformat()))
    conn.commit()
    client_id = cur.lastrowid
    conn.close()
    return {
        "id": client_id, "entreprise_id": entreprise_id, "session_id": session_id,
        "prenom": None, "telephone": None, "date_anniversaire": None,
        "latitude": None, "longitude": None,
    }


def maj_client(session_id, entreprise_id, prenom=None, telephone=None, date_anniversaire=None, latitude=None, longitude=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM clients WHERE entreprise_id = ? AND session_id = ?", (entreprise_id, session_id))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO clients (entreprise_id, session_id, date_creation)
            VALUES (?, ?, ?)
        """, (entreprise_id, session_id, datetime.utcnow().isoformat()))

    champs = []
    valeurs = []
    if prenom is not None:
        champs.append("prenom = ?")
        valeurs.append(prenom)
    if telephone is not None:
        champs.append("telephone = ?")
        valeurs.append(telephone)
    if date_anniversaire is not None:
        champs.append("date_anniversaire = ?")
        valeurs.append(date_anniversaire)
    if latitude is not None:
        champs.append("latitude = ?")
        valeurs.append(latitude)
    if longitude is not None:
        champs.append("longitude = ?")
        valeurs.append(longitude)
    if champs:
        valeurs += [entreprise_id, session_id]
        cur.execute(f"UPDATE clients SET {', '.join(champs)} WHERE entreprise_id = ? AND session_id = ?", valeurs)

    conn.commit()
    conn.close()


def ajouter_message(entreprise_id, session_id, role, contenu):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (entreprise_id, session_id, role, contenu, date_creation)
        VALUES (?, ?, ?, ?, ?)
    """, (entreprise_id, session_id, role, contenu, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def obtenir_historique(entreprise_id, session_id, limite=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, contenu FROM messages
        WHERE entreprise_id = ? AND session_id = ?
        ORDER BY id ASC
        LIMIT ?
    """, (entreprise_id, session_id, limite))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def creer_commande(entreprise_id, session_id, items, total, moyen_paiement=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO commandes (entreprise_id, session_id, items_json, total, moyen_paiement, date_creation)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entreprise_id, session_id, json.dumps(items), total, moyen_paiement, datetime.utcnow().isoformat()))
    conn.commit()
    commande_id = cur.lastrowid
    conn.close()
    return commande_id


def creer_rendez_vous(entreprise_id, session_id, creneau_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO rendez_vous (entreprise_id, session_id, creneau_id, date_creation)
        VALUES (?, ?, ?, ?)
    """, (entreprise_id, session_id, creneau_id, datetime.utcnow().isoformat()))
    conn.commit()
    rdv_id = cur.lastrowid
    conn.close()
    reserver_creneau(creneau_id)
    return rdv_id


def obtenir_dernier_rdv(entreprise_id, session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rv.id, rv.statut, c.libelle, c.jour, c.heure
        FROM rendez_vous rv
        JOIN creneaux c ON c.id = rv.creneau_id
        WHERE rv.entreprise_id = ? AND rv.session_id = ?
        ORDER BY rv.id DESC LIMIT 1
    """, (entreprise_id, session_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def obtenir_derniere_commande(entreprise_id, session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, total, moyen_paiement, statut, date_creation FROM commandes
        WHERE entreprise_id = ? AND session_id = ?
        ORDER BY id DESC LIMIT 1
    """, (entreprise_id, session_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def compter_commandes(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM commandes WHERE entreprise_id = ?", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return {"nombre": row[0], "total": row[1]}


def compter_rendez_vous(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rendez_vous WHERE entreprise_id = ?", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return row[0]


def compter_conversations(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT session_id) FROM messages WHERE entreprise_id = ?", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return row[0]


def obtenir_historique_commandes(entreprise_id, session_id, limite=5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, items_json, total, moyen_paiement, statut, date_creation FROM commandes
        WHERE entreprise_id = ? AND session_id = ?
        ORDER BY id DESC LIMIT ?
    """, (entreprise_id, session_id, limite))
    rows = cur.fetchall()
    conn.close()
    resultat = []
    for r in rows:
        items = json.loads(r["items_json"])
        resultat.append({
            "id": r["id"],
            "nb_articles": sum(i["quantite"] for i in items),
            "total": r["total"],
            "moyen_paiement": r["moyen_paiement"],
            "statut": r["statut"],
            "date_creation": r["date_creation"],
        })
    return resultat


def obtenir_historique_rdv(entreprise_id, session_id, limite=5):
    """Historique des rendez-vous passes par CE client (utilise cote secteur rendez-vous, panneau Historique)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rv.id, rv.statut, rv.date_creation, c.libelle, c.jour, c.heure
        FROM rendez_vous rv
        JOIN creneaux c ON c.id = rv.creneau_id
        WHERE rv.entreprise_id = ? AND rv.session_id = ?
        ORDER BY rv.id DESC LIMIT ?
    """, (entreprise_id, session_id, limite))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtenir_note(entreprise_id, session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT contenu FROM notes_client WHERE entreprise_id = ? AND session_id = ?", (entreprise_id, session_id))
    row = cur.fetchone()
    conn.close()
    return row["contenu"] if row else ""


def sauvegarder_note(entreprise_id, session_id, contenu):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notes_client (entreprise_id, session_id, contenu, date_maj)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(entreprise_id, session_id) DO UPDATE SET
            contenu = excluded.contenu, date_maj = excluded.date_maj
    """, (entreprise_id, session_id, contenu, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ---------- STATISTIQUES / COURBES ----------

def obtenir_stats_journalieres(entreprise_id, jours=7):
    """Retourne les stats jour par jour (pour les courbes) sur les N derniers jours."""
    conn = get_connection()
    cur = conn.cursor()
    resultat = []
    for i in range(jours - 1, -1, -1):
        jour = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")

        cur.execute(
            "SELECT COUNT(DISTINCT session_id) FROM messages WHERE entreprise_id = ? AND date_creation LIKE ?",
            (entreprise_id, jour + "%"),
        )
        conversations = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(total),0) FROM commandes WHERE entreprise_id = ? AND date_creation LIKE ?",
            (entreprise_id, jour + "%"),
        )
        row = cur.fetchone()
        commandes, chiffre_affaires = row[0], row[1]

        cur.execute(
            "SELECT COUNT(*) FROM rendez_vous WHERE entreprise_id = ? AND date_creation LIKE ?",
            (entreprise_id, jour + "%"),
        )
        rendez_vous = cur.fetchone()[0]

        resultat.append({
            "date": jour,
            "conversations": conversations,
            "commandes": commandes,
            "chiffre_affaires": chiffre_affaires,
            "rendez_vous": rendez_vous,
        })
    conn.close()
    return resultat


def obtenir_top_produits(entreprise_id, limite=6):
    """Agrege les articles les plus commandes a partir de l'historique des commandes."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT items_json FROM commandes WHERE entreprise_id = ?", (entreprise_id,))
    rows = cur.fetchall()
    conn.close()

    compteur = {}
    for r in rows:
        try:
            items = json.loads(r["items_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        for item in items:
            nom = item.get("nom", "?")
            compteur[nom] = compteur.get(nom, 0) + item.get("quantite", 1)

    trie = sorted(compteur.items(), key=lambda x: x[1], reverse=True)[:limite]
    return [{"nom": n, "quantite": q} for n, q in trie]


# ---------- LISTE DES CLIENTS (page Clients du dashboard) ----------

def obtenir_clients_entreprise(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM clients WHERE entreprise_id = ? ORDER BY date_creation DESC
    """, (entreprise_id,))
    clients = [dict(r) for r in cur.fetchall()]

    for c in clients:
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(total),0) FROM commandes
            WHERE entreprise_id = ? AND session_id = ?
        """, (entreprise_id, c["session_id"]))
        row = cur.fetchone()
        c["nb_commandes"] = row[0]
        c["total_depense"] = row[1]

        cur.execute("""
            SELECT COUNT(*) FROM rendez_vous WHERE entreprise_id = ? AND session_id = ?
        """, (entreprise_id, c["session_id"]))
        c["nb_rdv"] = cur.fetchone()[0]

        c["anniversaire_aujourdhui"] = est_anniversaire_aujourdhui(c.get("date_anniversaire"))

    conn.close()
    return clients


# ---------- COMMANDES (page Commandes du dashboard) ----------

def obtenir_commandes_entreprise(entreprise_id, statut=None):
    """Liste toutes les commandes d'une entreprise, avec les infos du client (pour contacter/livrer)."""
    conn = get_connection()
    cur = conn.cursor()
    if statut:
        cur.execute("""
            SELECT c.*, cl.prenom, cl.telephone, cl.latitude, cl.longitude
            FROM commandes c
            LEFT JOIN clients cl ON cl.entreprise_id = c.entreprise_id AND cl.session_id = c.session_id
            WHERE c.entreprise_id = ? AND c.statut = ?
            ORDER BY c.id DESC
        """, (entreprise_id, statut))
    else:
        cur.execute("""
            SELECT c.*, cl.prenom, cl.telephone, cl.latitude, cl.longitude
            FROM commandes c
            LEFT JOIN clients cl ON cl.entreprise_id = c.entreprise_id AND cl.session_id = c.session_id
            WHERE c.entreprise_id = ?
            ORDER BY c.id DESC
        """, (entreprise_id,))
    rows = cur.fetchall()
    conn.close()

    resultat = []
    for r in rows:
        d = dict(r)
        try:
            d["items"] = json.loads(d.pop("items_json"))
        except (json.JSONDecodeError, TypeError):
            d["items"] = []
        resultat.append(d)
    return resultat


def obtenir_commande(commande_id):
    """Recupere une commande precise avec les infos du client, pour generer le message livreur."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, cl.prenom, cl.telephone, cl.latitude, cl.longitude
        FROM commandes c
        LEFT JOIN clients cl ON cl.entreprise_id = c.entreprise_id AND cl.session_id = c.session_id
        WHERE c.id = ?
    """, (commande_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["items"] = json.loads(d.pop("items_json"))
    except (json.JSONDecodeError, TypeError):
        d["items"] = []
    return d


def changer_statut_commande(commande_id, statut):
    """statut attendu : nouvelle, en_preparation, en_livraison, livree, annulee"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE commandes SET statut = ? WHERE id = ?", (statut, commande_id))
    conn.commit()
    conn.close()


def marquer_commande_vue(commande_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE commandes SET vue = 1 WHERE id = ?", (commande_id,))
    conn.commit()
    conn.close()


def marquer_toutes_commandes_vues(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE commandes SET vue = 1 WHERE entreprise_id = ?", (entreprise_id,))
    conn.commit()
    conn.close()


def compter_commandes_non_vues(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM commandes WHERE entreprise_id = ? AND vue = 0", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return row[0]


# ---------- RENDEZ-VOUS (liste complete pour le dashboard) ----------

def obtenir_rendez_vous_entreprise(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rv.*, c.libelle, c.jour, c.heure, cl.prenom, cl.telephone
        FROM rendez_vous rv
        JOIN creneaux c ON c.id = rv.creneau_id
        LEFT JOIN clients cl ON cl.entreprise_id = rv.entreprise_id AND cl.session_id = rv.session_id
        WHERE rv.entreprise_id = ?
        ORDER BY rv.id DESC
    """, (entreprise_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def marquer_rdv_vue(rdv_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE rendez_vous SET vue = 1 WHERE id = ?", (rdv_id,))
    conn.commit()
    conn.close()


def marquer_tous_rdv_vus(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE rendez_vous SET vue = 1 WHERE entreprise_id = ?", (entreprise_id,))
    conn.commit()
    conn.close()


def compter_rdv_non_vus(entreprise_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rendez_vous WHERE entreprise_id = ? AND vue = 0", (entreprise_id,))
    row = cur.fetchone()
    conn.close()
    return row[0]