from mastodon import Mastodon
import pandas as pd
import csv
import re
import time
import os
import sys
import html

from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


# Ensure console output uses UTF-8 on Windows (prevents UnicodeEncodeError on emoji)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# --- Configuration ---
# Remplace ces valeurs par celles de ton application Mastodon
MASTODON_INSTANCE = "https://mastodon.social"  # URL de l'instance
CLIENT_ID = os.getenv("MASTODON_ID_APP")
CLIENT_SECRET = os.getenv("MASTODON_SECRET")
ACCESS_TOKEN = os.getenv("MASTODON_TOKEN_ACCESS")

# ID de l'utilisateur dont tu veux récupérer les messages (remplace par l'ID réel)
#USER_ID = "115854282414479268"  # Exemple : l'ID numérique de l'utilisateur (pas son pseudo)



# Configuration de l'API
mastodon = Mastodon(
    api_base_url="https://mastodon.social",  # Remplace par l'instance de l'utilisateur
    access_token=ACCESS_TOKEN  # Ton token d'accès
)

# Recherche un utilisateur par son pseudo (ex: "@utilisateur@mastodon.social")
# Utilise la variable d'environnement PSEUDO si fournie (server l'enverra)
pseudo = os.getenv("PSEUDO") or "compound Interest"  # Remplace par le pseudo de l'utilisateur
account = mastodon.account_search(pseudo, resolve=True)  # `resolve=True` pour obtenir l'ID

if account:
    USER_ID = account[0]["id"]  # ID numérique de l'utilisateur
    print(f"L'ID de l'utilisateur est : {USER_ID}")
else:
    print("Utilisateur non trouvé.")


# --- Fonctions utiles ---
def nettoyer_texte(texte):
    """Nettoie le HTML, décode entités et normalise le texte."""
    if not texte:
        return ""
    # Supprime attributs indésirables qui apparaissent parfois dans le contenu
    texte = re.sub(r'class="?[^">]*ellipsis[^">]*"?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'class="?[^">]*mention[^">]*"?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'class="?[^">]*invisible[^">]*"?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'class="?[^">]*u-url[^">]*"?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'(target|rel|translate)=?"[^"]*"', '', texte, flags=re.IGNORECASE)
    # Enlever autres paires attribut="..." résiduelles
    texte = re.sub(r'\b[a-zA-Z_-]+="[^"]*"', '', texte)
    # Décoder entités HTML (&amp; etc.)
    texte = html.unescape(texte)
    # Supprimer balises HTML
    texte = re.sub(r'<[^>]+>', '', texte)
    # Supprimer mentions et hashtags restants
    texte = re.sub(r'@\w+', '', texte)
    texte = re.sub(r'#\w+', '', texte)
    # Normaliser espaces
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte

def anonymiser_id(user_id):
    """Génère un ID aléatoire à partir de l'ID utilisateur."""
    return f"user_{user_id[-5:]}"  # Ex : user_23456

# --- Connexion à Mastodon ---
mastodon = Mastodon(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    access_token=ACCESS_TOKEN,
    api_base_url=MASTODON_INSTANCE
)

# --- Récupération des messages ---
try:
    print(f"Recuperation des messages pour l'utilisateur {USER_ID}:")
    posts = mastodon.account_statuses(USER_ID, limit=100)  # Récupère les 100 derniers posts

    # Préparation des données pour le CSV
    données = []
    for post in posts:
        user_id_anonymisé = anonymiser_id(USER_ID)
        message_nettoyé = nettoyer_texte(post.get("content", ""))

        # Récupérer les URLs des pièces jointes média (images, vidéos, etc.)
        media_attachments = post.get("media_attachments", []) or []
        media_urls = []
        for m in media_attachments:
            url = m.get("url") or m.get("remote_url") or m.get("preview_url")
            if url:
                media_urls.append(url)

        données.append({
            "user_id": user_id_anonymisé,
            "message": message_nettoyé,
            "date": post.get("created_at"),
            "media_urls": ";".join(media_urls)
        })

    # --- Sauvegarde dans un CSV ---
    df = pd.DataFrame(données)
    df.to_csv("social_media_data.csv", index=False, encoding="utf-8-sig")
    print("Data saved in 'social_media_data.csv' file.")

except Exception as e:
    print(f"Erreur lors de la récupération des messages : {e}")

# --- Exemple d'affichage ---
print("\n--- Exemple des données collectées (anonymisées) ---")
for i, post in enumerate(données[:3]):  # Affiche les 3 premiers messages
    print(f"\nMessage {i+1}:")
    print(f"ID utilisateur: {post['user_id']}")
    print(f"Date: {post['date']}")
    print(f"Contenu: {post['message']}")
    print(f"Media URLs: {post.get('media_urls','')}")

