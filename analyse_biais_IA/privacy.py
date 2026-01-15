# privacy.py
# Étape 1 — Privacy filter RGPD (anonymisation) + mode dossier (run_step1)

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, Tuple

# --- Patterns RGPD (identifiants directs) ---
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s]+\b|\bwww\.[^\s]+\b")
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,30}\b")

# IPv4 (simple et robuste)
IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)

# Hash / token hex long (MD5/SHA1/SHA256 etc. + autres tokens hex)
TOKEN_RE = re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)

# Téléphone FR (ex: 06 12 34 56 78 / 0612345678 / +33 6 12 34 56 78)
PHONE_RE = re.compile(r"\b(?:\+33|0)\s*(?:[1-9](?:[\s.-]?\d{2}){4})\b")


def privacy_filter(text: str, enable_ip: bool = True, enable_token: bool = True) -> Tuple[str, Dict[str, int]]:
    """
    Remplace les identifiants directs par des tags (<EMAIL>, <PHONE>, etc.)
    et retourne (texte_anonymisé, stats_de_masquage).
    """
    counts = defaultdict(int)
    t = text

    def sub(regex: re.Pattern, tag: str, key: str):
        nonlocal t
        matches = regex.findall(t)
        if matches:
            counts[key] += len(matches)
            t = regex.sub(tag, t)

    # Ordre important: URL avant EMAIL (parfois présent dans des query params)
    sub(URL_RE, "<URL>", "URL")
    sub(EMAIL_RE, "<EMAIL>", "EMAIL")
    sub(HANDLE_RE, "<HANDLE>", "HANDLE")

    if enable_ip:
        sub(IP_RE, "<IP>", "IP")
    if enable_token:
        sub(TOKEN_RE, "<TOKEN>", "TOKEN")

    sub(PHONE_RE, "<PHONE>", "PHONE")

    # Normalisation espaces
    t = re.sub(r"\s+", " ", t).strip()
    return t, dict(counts)


def run_step1(raw_dir: str, clean_dir: str, enable_ip: bool = True, enable_token: bool = True) -> Dict[str, int]:
    """
    Traite tous les fichiers .txt dans raw_dir, écrit leur version anonymisée dans clean_dir
    (même nom de fichier), et retourne un dictionnaire de stats globales.
    """
    raw = Path(raw_dir)
    clean = Path(clean_dir)
    clean.mkdir(exist_ok=True)

    if not raw.exists():
        raise FileNotFoundError(f"Dossier introuvable: {raw_dir}")

    global_counts = defaultdict(int)
    txt_files = sorted(raw.glob("*.txt"))

    if not txt_files:
        raise FileNotFoundError(f"Aucun fichier .txt trouvé dans: {raw_dir}")

    for p in txt_files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        clean_txt, counts = privacy_filter(txt, enable_ip=enable_ip, enable_token=enable_token)

        out_path = clean / p.name
        out_path.write_text(clean_txt, encoding="utf-8")

        for k, v in counts.items():
            global_counts[k] += v

    return dict(global_counts)


# --- Optionnel: exécution directe ---
# Usage simple:
#  - mets un fichier input.txt à côté de privacy.py
#  - lance: python privacy.py
#  - ça crée ./clean/input.txt anonymisé
if __name__ == "__main__":
    stats = run_step1(raw_dir=".", clean_dir="clean", enable_ip=True, enable_token=True)
    print("=== STATS (global) ===")
    print(stats)
    print("Fichiers anonymisés écrits dans ./clean/")
