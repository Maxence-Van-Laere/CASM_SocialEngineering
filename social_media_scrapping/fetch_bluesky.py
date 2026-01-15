from atproto import Client
import pandas as pd
import re
import time
import os
import sys
import html
from datetime import datetime, timezone

from dotenv import load_dotenv
import io
import traceback

# Charger les variables d'environnement
load_dotenv()

# Ensure console output uses UTF-8 on Windows (prevents UnicodeEncodeError on emoji)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
else:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# --- Configuration ---
# Remplace ces valeurs par celles de ton compte Bluesky
BLUESKY_IDENTIFIANT = os.getenv("BLUESKY_IDENTIFIANT") 
BLUESKY_MOT_DE_PASSE = os.getenv("BLUESKY_MOT_DE_PASSE")

# Identifiant de l'utilisateur dont tu veux récupérer les messages (remplace par l'identifiant réel)
# Permet d'utiliser la variable d'environnement PSEUDO si fournie par le serveur
USER_IDENTIFIANT = os.getenv("PSEUDO") #or "bgormley.bsky.social"


def normalize_actor(ident: str) -> str:
    """Normalise divers formats d'identifiant en handle Bluesky attendu.

    Accepts:
      - 'user' -> 'user.bsky.social' (ajoute domaine par défaut)
      - 'user@bsky.social' -> 'user.bsky.social'
      - 'user.bsky.social' -> unchanged
      - 'did:...' -> unchanged
    """
    if not ident:
        return ident
    s = ident.strip()
    # remove all whitespace inside the identifier (users sometimes paste spaces)
    s = re.sub(r"\s+", "", s)
    # remove leading @ if present
    if s.startswith('@'):
        s = s[1:]
    # transform user@instance -> user.instance
    if '@' in s and '.' not in s:
        s = s.replace('@', '.')
    # if no domain part and not a DID, append default Bluesky host
    if ('.' not in s) and (not s.startswith('did:')):
        s = f"{s}.bsky.social"
    return s


def is_valid_actor(s: str) -> bool:
    """Retourne True si `s` est un DID ou un handle valide (ex: user.bsky.social)."""
    if not s:
        return False
    if s.startswith('did:'):
        return True
    # handle should contain at least one dot and allowed chars
    return bool(re.match(r'^[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+$', s))


def pretty_error_and_exit(user_input: str, actor_input: str, reason: str = None):
    """Affiche un message d'erreur clair et quitte avec code 1."""
    sep = "=" * 72
    print("\n" + sep)
    print("ERREUR : profil introuvable / identifiant invalide".center(72))
    print("-" * 72)
    print(f"Saisie fournie : {user_input}")
    print(f"Valeur utilisée pour la requête : {actor_input}")
    if reason:
        print("\nDétail technique :")
        # keep reason short if it's long
        r = reason if len(reason) < 800 else reason[:800] + "..."
        print(r)
    print("\nSuggestions :")
    print(" - Vérifiez l'orthographe (ex : alice.bsky.social)")
    print(" - Utilisez le format 'user.instance' ou un DID (ex : did:plc:...)")
    print(" - Vous pouvez aussi essayer 'user@instance' (sera converti)")
    print(sep + "\n", flush=True)
    sys.exit(1)

# --- Fonctions utiles ---
def nettoyer_texte(texte):
    """Nettoie le texte:
    - décode entités HTML
    - transforme les liens HTML <a>...</a> en leur texte affiché
    - transforme les liens markdown [text](url) en 'text'
    - supprime les balises HTML restantes
    - supprime mentions et hashtags tout en conservant les URLs collées
    """
    if not texte:
        return ""
    # Décoder entités HTML
    texte = html.unescape(texte)
    # Remplacer les liens HTML <a href="url">text</a> par 'text (url)'
    def _anchor_repl(m):
        href = m.group(1)
        anchor_text = m.group(2)
        # convertir les liens relatifs en absolus (base Bluesky)
        if href.startswith('/'):
            href = 'https://bsky.app' + href
        return f"{anchor_text} ({href})"

    texte = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', _anchor_repl, texte, flags=re.IGNORECASE | re.DOTALL)
    # Remplacer les liens markdown [text](url) par 'text (url)'
    texte = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r"\1 (\2)", texte)
    # Supprimer balises HTML restantes
    texte = re.sub(r'<[^>]+>', '', texte)
    # Conserver les URLs collées même sans protocole (ex: example.com/path)
    # (on ne les supprime pas)
    # Conserver les mentions (@handle) mais supprimer hashtags
    texte = re.sub(r'#\w+', '', texte)
    # Normaliser espaces
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte

def anonymiser_id(user_identifiant):
    """Génère un ID aléatoire à partir de l'identifiant utilisateur."""
    return f"user_{hash(user_identifiant) % 100000}"  # Ex : user_12345


def parse_iso_datetime(value):
    """Parse une date ISO ou retourne None. Gère le suffixe Z."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value)
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        # fromisoformat gère le format avec offset
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # fallback: try to parse date portion
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z")
        except Exception:
            try:
                return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
            except Exception:
                return None


def format_timedelta(delta):
    """Return a short human readable delta like '2d 3h'"""
    if delta is None:
        return "unknown"
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = abs(seconds)
    periods = [
        ('y', 60 * 60 * 24 * 365),
        ('mo', 60 * 60 * 24 * 30),
        ('d', 60 * 60 * 24),
        ('h', 60 * 60),
        ('m', 60),
        ('s', 1),
    ]
    parts = []
    for name, count in periods:
        if seconds >= count:
            value = seconds // count
            seconds -= value * count
            parts.append(f"{value}{name}")
        if len(parts) >= 2:
            break
    return ' '.join(parts) + ' ago' if parts else '0s ago'

# --- Connexion à Bluesky ---
client = Client()
client.login(BLUESKY_IDENTIFIANT, BLUESKY_MOT_DE_PASSE)

# --- Récupération des messages ---
try:
    print(f"Récupération des messages pour l'utilisateur {USER_IDENTIFIANT}...")

    # Préparer la liste de résultats (évite NameError en cas d'exception)
    données = []

    # Récupère le profil de l'utilisateur pour obtenir son DID (identifiant décentralisé)
    try:
        # normalise l'acteur fourni par l'utilisateur pour accepter plusieurs formats
        actor_ns = client.app.bsky.actor
        actor_input = normalize_actor(USER_IDENTIFIANT)
        print(f"DEBUG: actor input normalisé -> {actor_input}")
        # validate normalized input: must be a DID or a handle (user.domain)
        if not is_valid_actor(actor_input):
            pretty_error_and_exit(USER_IDENTIFIANT, actor_input, reason="Format invalide après normalisation")
        # Essayer plusieurs noms de méthodes possibles selon la version du SDK
        profile_method = None
        for name in ("getProfile", "get_profile", "profile", "getProfileView"):
            if hasattr(actor_ns, name):
                profile_method = getattr(actor_ns, name)
                break

        if profile_method is None:
            # Débogage: lister les attributs disponibles
            print("DEBUG: méthodes disponibles dans client.app.bsky.actor:", dir(actor_ns))
            raise AttributeError("Aucune méthode connue pour récupérer le profil sur 'actor' namespace")

        # Appeler la méthode trouvée
        try:
            profile_resp = profile_method({"actor": actor_input})
        except TypeError:
            # Parfois la signature attend une simple string
            profile_resp = profile_method(actor_input)

        # profile_resp peut être {'data': {...}} ou un objet; récupérer proprement les données
        if isinstance(profile_resp, dict):
            profile_data = profile_resp.get("data", profile_resp)
        else:
            profile_data = getattr(profile_resp, "data", profile_resp)

        user_did = None
        if isinstance(profile_data, dict):
            user_did = profile_data.get("did") or profile_data.get("handle")
        else:
            user_did = getattr(profile_data, "did", None) or getattr(profile_data, "handle", None)

        # If profile lookup did not return a did/handle, stop execution and report
        if not user_did:
            pretty_error_and_exit(USER_IDENTIFIANT, actor_input, reason="Profil introuvable (aucun DID/handle retourné)")

        actor_for_feed = user_did or actor_input

    except Exception as e_profile:
        # Print a concise, user-friendly error and exit
        msg = str(e_profile)
        pretty_error_and_exit(USER_IDENTIFIANT, actor_input, reason=msg)

    # Récupère les 50 derniers messages publics de l'utilisateur (robuste selon version du SDK)
    try:
        feed_ns = client.app.bsky.feed
        feed_method = None
        # essayer variantes courantes de nommage
        for name in ("get_author_feed", "getAuthorFeed", "get_authorFeed", "get_author_feed"):
            if hasattr(feed_ns, name):
                feed_method = getattr(feed_ns, name)
                chosen_name = name
                break

        if feed_method is None:
            print("DEBUG: méthodes disponibles dans client.app.bsky.feed:", dir(feed_ns))
            raise AttributeError("Aucune méthode connue pour récupérer le feed sur 'feed' namespace")

        # appeler la méthode choisie (certaines signatures acceptent un dict, d'autres des kwargs/args)
        try:
            print(f"DEBUG: appel de la méthode de feed: {chosen_name}")
            posts_resp = feed_method({"actor": actor_for_feed, "limit": 100})
        except TypeError:
            try:
                posts_resp = feed_method(actor_for_feed, 100)
            except Exception:
                posts_resp = feed_method(actor=actor_for_feed, limit=100)

    except Exception as e_feed:
        # concise error for feed retrieval failures
        pretty_error_and_exit(USER_IDENTIFIANT, actor_for_feed, reason=str(e_feed))

    # Extraire la liste de posts quel que soit le format retourné
    if isinstance(posts_resp, dict) and "data" in posts_resp and "feed" in posts_resp["data"]:
        feed = posts_resp["data"]["feed"]
    elif isinstance(posts_resp, dict) and "feed" in posts_resp:
        feed = posts_resp["feed"]
    else:
        # essayer attributs d'objet
        feed = getattr(posts_resp, "feed", None) or getattr(posts_resp, "data", None) or []

    # Normaliser en liste
    if feed is None:
        feed = []

    for item in feed:
        # différents wrappers possibles : item peut être dict avec clé 'post', ou objet
        record = None
        indexed_at = None
        if isinstance(item, dict):
            post_obj = item.get("post") or item.get("postRecord") or item
            if isinstance(post_obj, dict) and "record" in post_obj:
                record = post_obj["record"]
                indexed_at = post_obj.get("indexedAt") or post_obj.get("indexed_at")
            elif isinstance(post_obj, dict) and "text" in post_obj:
                record = post_obj
                indexed_at = item.get("indexedAt") or item.get("indexed_at") or post_obj.get("indexedAt")
        else:
            # objet avec attributs
            post_obj = getattr(item, "post", None) or item
            record = getattr(post_obj, "record", None) or post_obj
            indexed_at = getattr(post_obj, "indexedAt", None) or getattr(item, "indexed_at", None) or getattr(item, "indexedAt", None)

        if not record:
            continue

        user_id_anonymisé = anonymiser_id(USER_IDENTIFIANT)
        text = None
        if isinstance(record, dict):
            text = record.get("text") or record.get("content")
        else:
            text = getattr(record, "text", None) or getattr(record, "content", None)

        if not text:
            continue

        message_nettoyé = nettoyer_texte(text)
        # Préférer le champ 'createdAt' dans le record si présent (format JSON de post)
        created_at = None
        if isinstance(record, dict):
            created_at = record.get("createdAt") or record.get("created_at") or indexed_at
        else:
            created_at = getattr(record, "createdAt", None) or getattr(record, "created_at", None) or indexed_at

        # parser la date et calculer le temps écoulé (utilise created_at si disponible)
        parsed = parse_iso_datetime(created_at)
        # Normaliser parsed en timezone-aware UTC
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - parsed
            age = format_timedelta(delta)
            date_iso = parsed.isoformat()
            # Formater en heure locale lisible
            try:
                local_dt = parsed.astimezone()
                date_pretty = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                date_pretty = parsed.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            age = "unknown"
            date_iso = indexed_at
            date_pretty = "unknown"

        # Conserver une seule colonne 'date' bien formatée (locale) et la colonne 'age'
        données.append({
            "user_id": user_id_anonymisé,
            "message": message_nettoyé,
            "date": date_pretty if parsed is not None else (date_iso if date_iso is not None else "unknown"),
            "age": age
        })

    # --- Sauvegarde dans un CSV ---
    df = pd.DataFrame(données)
    df.to_csv("social_media_data.csv", index=False, encoding="utf-8")
    print("Données sauvegardées dans 'social_media_data.csv'.")

except Exception as e:
    print(f"Erreur lors de la récupération des messages : {e}")

# --- Exemple d'affichage ---
print("\n--- Exemple des données collectées (anonymisées) ---")
for i, post in enumerate(données[:3]):  # Affiche les 3 premiers messages
    print(f"\nMessage {i+1}:")
    print(f"ID utilisateur: {post['user_id']}")
    print(f"Date: {post['date']} ({post.get('age','unknown')})")
    print(f"Contenu: {post['message']}")
