import os
import json
import requests
from urllib.parse import quote
from dotenv import load_dotenv


# Charger les variables d'environnement
load_dotenv()

# Forcer la sortie console en UTF-8 pour éviter les UnicodeEncodeError sur Windows
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import re
import argparse
import random
import time


def sanitize_query(query: str) -> str:
        """Normalise une query pour remplacer les opérateurs 'filter' non supportés.

        Exemples de transformations:
            - "-filter:links" -> "-has:links"
            - "-filter:retweets" -> "-is:retweet"
            - "filter:links" -> "has:links"
        """
        orig = query
        q = query
        # remplacements simples et sûrs
        q = q.replace("-filter:links", "-has:links")
        q = q.replace("-filter:retweets", "-is:retweet")
        q = q.replace("filter:links", "has:links")
        q = q.replace("filter:retweets", "is:retweet")

        # Nettoyage d'espacements éventuels
        q = re.sub(r"\s+", " ", q).strip()

        if q != orig:
                print(f"🔧 Query normalisée: {q}")
        return q

print("Bearer token:", os.getenv("TWITTER_BEARER_TOKEN"))

def fetch_user_tweets(query="(#BlackFriday OR #Promo) lang:fr -is:retweet -has:links", count=10, output_file="tweets_raw.json", start_time=None, end_time=None):
    """
    Récupère des tweets d'utilisateurs avec une requête optimisée.
    Args:
        query (str): Requête filtrée (ex: "(#BlackFriday OR #Promo) lang:fr -is:retweet -has:links").
        count (int): Nombre de tweets (max 100 par requête).
        output_file (str): Fichier de sortie.
    Returns:
        list: Tweets récupérés.
    """
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        raise ValueError("Bearer Token manquant.")

    headers = {"Authorization": f"Bearer {bearer_token}"}
    # Normaliser la query pour éviter les opérateurs non supportés
    query = sanitize_query(query)
    encoded_query = quote(query)
    used_count = min(max(count, 10), 100)
    # demander des champs supplémentaires pour l'analyse et l'agrégation par auteur
    tweet_fields = "text,author_id,created_at,public_metrics,lang"
    expansions = "author_id"
    user_fields = "username,description,location,public_metrics"
    url = f"https://api.twitter.com/2/tweets/search/recent?query={encoded_query}&max_results={used_count}&tweet.fields={tweet_fields}&expansions={expansions}&user.fields={user_fields}"
    if start_time:
        url += f"&start_time={quote(start_time)}"
    if end_time:
        url += f"&end_time={quote(end_time)}"

    try:
        print(f"🔍 Requête API: demande {used_count} tweets (retour limité à {count}) pour : {query}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tweets_data = response.json()

        if "errors" in tweets_data:
            print(f"⚠️ Erreur API : {tweets_data['errors']}")
            return []

        tweets = []
        # build map of users from includes
        users_map = {u['id']: u for u in tweets_data.get('includes', {}).get('users', [])}
        for tweet in tweets_data.get("data", []):
            tid = tweet.get('id')
            author_id = tweet.get('author_id')
            user = users_map.get(author_id, {})
            tweets.append({
                "id": tid,
                "text": tweet.get("text", ""),
                "author_id": author_id,
                "author_username": user.get('username'),
                "author_description": user.get('description'),
                "created_at": tweet.get('created_at'),
                "lang": tweet.get('lang'),
                "public_metrics": tweet.get('public_metrics', {})
            })

        # Retourner seulement jusqu'à `count` éléments demandés par l'appel
        if count and count > 0:
            tweets = tweets[:count]

        print(f"✅ {len(tweets)} tweets récupérés (objet enrichi).")
        return tweets

    except requests.exceptions.HTTPError as e:
        resp = e.response
        print(f"⚠️ Erreur HTTP {resp.status_code} : {resp.text}")
        return []
    except Exception as e:
        print(f"⚠️ Erreur : {e}")
        return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Récupérer et diversifier des tweets (search recent)")
    parser.add_argument("--queries", "-q", help="Requêtes séparées par '||' (ex: '#BlackFriday || #Promo')",
                        default="#BlackFriday lang:fr -filter:links -filter:retweets")
    parser.add_argument("--count", "-c", type=int, help="Nombre total de tweets à récupérer (par défaut 10)", default=10)
    parser.add_argument("--sample", "-s", type=int, help="Taille d'échantillon à garder après fusion (0 = garder tous)", default=0)
    parser.add_argument("--output", "-o", help="Fichier de sortie JSON", default="tweets_raw.json")
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split("||") if q.strip()]
    if not queries:
        queries = ["#BlackFriday lang:fr -filter:links -filter:retweets"]

    # Répartir le nombre demandé entre les queries (au moins 1 par requête en terme de besoin final)
    per_query = max(1, args.count // len(queries))

    all_tweets = []
    seen_texts = set()

    # Charger les tweets déjà sauvegardés (si le fichier existe) pour éviter les doublons inter-exécutions
    if os.path.exists(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing = json.load(f)
            loaded = 0
            for item in existing:
                text = item.get("text")
                if text:
                    seen_texts.add(text)
                    loaded += 1
            if loaded:
                print(f"🔁 {loaded} tweets existants chargés depuis {args.output} — ils seront ignorés.")
        except Exception as e:
            print(f"⚠️ Impossible de charger {args.output} : {e}")

    for q in queries:
        try:
            fetched = fetch_user_tweets(query=q, count=per_query, output_file=args.output)
        except Exception as e:
            print(f"Erreur lors de la récupération pour la query '{q}': {e}")
            fetched = []

        for t in fetched:
            text = t.get("text")
            if text and text not in seen_texts:
                seen_texts.add(text)
                all_tweets.append(t)

        # Petitte pause pour réduire le risque de rate limit
        time.sleep(1)

    # Si sample demandé, échantillonner aléatoirement
    if args.sample and args.sample > 0 and len(all_tweets) > args.sample:
        all_tweets = random.sample(all_tweets, args.sample)

    # Troncation finale pour respecter exactement le nombre demandé
    if args.count and args.count > 0 and len(all_tweets) > args.count:
        all_tweets = all_tweets[: args.count]

    # Sauvegarder le résultat final
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_tweets, f, ensure_ascii=False, indent=2)

    print(f"--- Tweets finaux ({len(all_tweets)}) sauvegardés dans {args.output} ---")
    print(json.dumps(all_tweets, ensure_ascii=False, indent=2))
