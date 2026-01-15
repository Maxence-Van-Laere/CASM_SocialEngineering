import csv
import json
from pathlib import Path

import privacy
import cognitive_engine

# Input CSV attendu (colonne `message`)
INPUT_CSV = "social_media_data.csv"

# Make paths relative to this script's directory (analyse_biais_IA/)
BASE_DIR = Path(__file__).parent
CLEAN_DIR = BASE_DIR / "clean"
OUTPUT_DIR = BASE_DIR / "output"


def resolve_input_csv(name: str) -> Path:
    """Try several locations for the input CSV and return a Path.

    Order:
    1. `analyse_biais_IA/<name>` (same folder as this script)
    2. parent project root `../<name>`
    3. current working directory `<name>`
    """
    candidates = [BASE_DIR / name, BASE_DIR.parent / name, Path(name)]
    for p in candidates:
        if p.exists():
            return p
    # fallback: return the first candidate (for nicer error message)
    return candidates[0]


def read_messages_from_csv(path) -> str:
    """Lit la colonne `message` d'un CSV et concatène tous les messages.

    `path` peut être une `str` ou un `Path`.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Fichier CSV introuvable: {p}")

    parts = []
    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.DictReader(fh)
        # Si la colonne 'message' n'existe pas, on tente la première colonne restante
        for row in reader:
            if "message" in row and row["message"] is not None:
                parts.append(row["message"].strip())
            else:
                # fallback: concatène toutes les valeurs de la ligne
                parts.append(" ".join([v for v in row.values() if v]))

    return "\n".join([p for p in parts if p])


def main():
    # Lire les messages depuis le CSV
    try:
        input_path = resolve_input_csv(INPUT_CSV)
        text = read_messages_from_csv(input_path)
    except FileNotFoundError as e:
        print(f"Erreur: {e}")
        return

    # Étape 1 RGPD (anonymisation)
    anonymized, stats = privacy.privacy_filter(text)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    # On conserve le nom input.txt dans clean/ pour compatibilité
    (CLEAN_DIR / "input.txt").write_text(anonymized, encoding="utf-8")

    print("[OK] Étape 1 RGPD — CSV traité:", str(input_path))
    print("Stats:", stats)

    # Étape 2 Analyse cognitive
    engine = cognitive_engine.CognitiveMetricsEngine()
    schema = engine.analyze(anonymized)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("[OK] Étape 2 Analyse")
    print("Résultat dans:", str(OUTPUT_DIR / "schema.json"))


if __name__ == "__main__":
    main()
