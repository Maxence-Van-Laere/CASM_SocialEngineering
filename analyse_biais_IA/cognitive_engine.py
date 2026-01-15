import re
from collections import Counter
from typing import Dict, List, Optional

WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_]+")
SENT_SPLIT_RE = re.compile(r"[.!?]+")
HASHTAG_RE = re.compile(r"#(\w+)")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")

def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

class CognitiveMetricsEngine:
    def __init__(self, enable_hf_emotions: bool = True):
        # ---------- RULE-BASED LEXICONS ----------
        self.lexicon_words: Dict[str, List[str]] = {
            "self": ["je", "moi", "mon", "ma", "mes", "m", "j"],
            "group": ["nous", "notre", "nos", "équipe", "equipe", "on", "ensemble", "team"],
            "other": ["tu", "vous", "ton", "votre", "tes", "vos", "toi"],

            "tech": [
                "api", "code", "data", "server", "serveur", "cloud", "ai", "ia",
                "rust", "python", "bug", "k8s", "kubernetes", "microservices", "microservice",
                "latence", "migration", "architecture", "devops", "prod", "ci", "cd",
                "docker", "linux", "backend", "frontend", "git", "github", "jwt", "oauth", "mfa", "2fa"
            ],

            "conflict": [
                "faux", "erreur", "problème", "probleme", "inacceptable", "inadmissible",
                "honteux", "ridicule", "catastrophe", "nul", "pire"
            ],

            "help": [
                "aide", "svp", "stp", "besoin", "support", "bloqué", "bloque", "merci",
                "renfort", "renforts", "aidez", "help"
            ],

            "urgency": [
                "vite", "asap", "urgent", "urgente", "maintenant", "deadline",
                "immédiatement", "immediatement", "rapidement", "aujourd'hui", "auj",
                "livrer", "livraison"
            ],

            "authority": [
                "chef", "manager", "directeur", "direction", "ceo", "cto", "rh", "hr",
                "administration", "conformité", "conformite", "règlement", "reglement",
                "procédure", "procedure", "validation", "valider", "approuver", "ordre"
            ],

            "money": [
                "prix", "coût", "cout", "euro", "argent", "gratuit", "offre",
                "paiement", "virement", "iban", "facture", "budget", "salaire"
            ],

            "absolutism": ["toujours", "jamais", "absolument", "obligatoire", "impératif", "imperatif"],
            "hedging": ["peut", "peutêtre", "peut-être", "semble", "crois", "possible", "probablement"],

            "future": ["demain", "bientôt", "projet", "objectif", "avenir", "phase", "prochaine", "ensuite", "future"],
            "past": ["hier", "déjà", "deja", "passé", "passe", "avant-hier", "dernier"],

            # fear lexique : on le garde, mais HF fera mieux
            "fear": ["peur", "risque", "menace", "sanction", "bloqué", "bloque", "suspendu", "danger", "fraude"]
        }

        self.lexicon_phrases: Dict[str, List[str]] = {
            "urgency": [
                "pas le temps", "sous l'eau", "sous l’eau", "tout de suite",
                "dans l'heure", "dans l’heure", "avant la fin", "fin du mois",
                "avant la fin du mois", "au plus vite", "trop lent", "on doit livrer"
            ],
            "authority": ["la direction", "les rh", "service informatique"],
            "hedging": ["je crois", "je pense", "il me semble", "à confirmer"],
            "imperative": ["merci de", "veuillez", "prière de", "priere de"]
        }

        self.imperative_verbs = {
            "envoie", "envoyez", "envois", "envoi",
            "appelle", "appelez",
            "contacte", "contactez",
            "réponds", "répondez", "reponds", "repondez",
            "clique", "cliquez",
            "valide", "validez", "valider",
            "donne", "donnez",
            "transferer", "transferez",
            "ouvre", "ouvrez",
            "remplis", "remplissez"
        }

        self.intensifiers = {
            "vraiment", "littéralement", "honnetement", "honnêtement", "trop",
            "tellement", "grave", "énorme", "enorme", "hyper", "enfin", "bam", "incroyable"
        }

        self._lex_sets = {k: set(v) for k, v in self.lexicon_words.items()}

        # ---------- HF EMOTIONS (OPTIONAL) ----------
        self.emotion_model: Optional[object] = None
        if enable_hf_emotions:
            try:
                from hf_emotions import EmotionHF
                self.emotion_model = EmotionHF()
            except Exception:
                self.emotion_model = None

    def _count_words(self, words: List[str]) -> Dict[str, int]:
        counts = {k: 0 for k in self._lex_sets.keys()}
        for w in words:
            for cat, s in self._lex_sets.items():
                if w in s:
                    counts[cat] += 1
        return counts

    def _count_phrases(self, text_lower: str) -> Dict[str, int]:
        counts = Counter()
        for cat, phrases in self.lexicon_phrases.items():
            for p in phrases:
                if p in text_lower:
                    counts[cat] += text_lower.count(p)
        return dict(counts)

    def analyze(self, text: str) -> dict:
        text_lower = text.lower()

        words = WORD_RE.findall(text_lower)
        sentences = [s for s in SENT_SPLIT_RE.split(text) if s.strip()]

        total_words = len(words) or 1
        total_sentences = len(sentences) or 1
        unique_words = len(set(words))

        word_counts = self._count_words(words)
        phrase_counts = self._count_phrases(text_lower)

        # Hits combinés
        urgency_hits = word_counts["urgency"] + phrase_counts.get("urgency", 0)
        authority_hits = word_counts["authority"] + phrase_counts.get("authority", 0)
        hedging_hits = word_counts["hedging"] + phrase_counts.get("hedging", 0)

        # Structural
        exclam_count = text.count("!")
        question_count = text.count("?")
        emoji_count = len(EMOJI_RE.findall(text))
        hashtag_words = [m.group(1).lower() for m in HASHTAG_RE.finditer(text)]
        hashtag_count = len(hashtag_words)

        caps_ratio = _safe_div(sum(1 for c in text if c.isupper()), len(text))
        intens_hits = sum(1 for w in words if w in self.intensifiers)

        # emotion (rules)
        emotion_rules = (
            _safe_div(exclam_count, total_sentences) * 0.35
            + caps_ratio * 0.35
            + _safe_div(emoji_count, total_sentences) * 0.20
            + _safe_div(intens_hits, total_sentences) * 0.10
        )
        emotion_rules = _clamp01(emotion_rules)

        # Imperative
        imperative_phrase_hits = phrase_counts.get("imperative", 0)
        imperative_verb_hits = sum(1 for w in words if w in self.imperative_verbs)

        imperative_substring_hits = 0
        for v in ["envoie", "appelle", "contacte", "répond", "clique", "valide", "donne", "transf"]:
            if v in text_lower:
                imperative_substring_hits += 1

        imperative_hits = imperative_phrase_hits + imperative_verb_hits + imperative_substring_hits
        imperative_ratio = _safe_div(imperative_hits, total_sentences)

        # Temporal focus (corrigé)
        future_hits = word_counts["future"]
        past_hits = word_counts["past"]
        if "fin du mois" in text_lower or "avant la fin" in text_lower:
            future_hits += 2

        temporal_focus = "present"
        if future_hits > past_hits + 1:
            temporal_focus = "future"
        elif past_hits > future_hits + 1:
            temporal_focus = "past"

        # Tech (hashtags bonus)
        tech_hits = word_counts["tech"]
        for h in hashtag_words:
            if h in ["tech", "rust", "kubernetes", "k8s", "microservices", "devops", "hiring"]:
                tech_hits += 1

        # ---- Rule scores ----
        urgency_rule = _safe_div(urgency_hits, total_words)
        authority_rule = _safe_div(authority_hits, total_words)
        fear_rule = _safe_div(word_counts["fear"], total_words)
        social_proof_rule = _safe_div(word_counts["group"], total_words)

        # ---- HF emotions scores (optional) ----
        ml_emotions = None
        fear_ml = 0.0
        emotion_ml = 0.0

        if self.emotion_model is not None:
            try:
                ml_emotions = self.emotion_model.scores(text)

                # Selon le modèle, les labels changent. On gère les variantes courantes :
                # fear / sadness / anger / joy etc.
                fear_ml = max(
                    ml_emotions.get("fear", 0.0),
                    ml_emotions.get("anxiety", 0.0),
                    ml_emotions.get("panic", 0.0)
                )
                # Intensité émotionnelle ML = score max (ou somme clampée)
                emotion_ml = max(ml_emotions.values()) if ml_emotions else 0.0
            except Exception:
                ml_emotions = None

        # ---- Fusion (gain en précision) ----
        # Idée : fear = max(rule, ml) ; emotion_intensity = max(rule, ml)
        # Urgence/autorité restent en rules (HF émotions ne score pas l'urgence)
        fear_final = max(fear_rule, fear_ml)
        emotion_final = max(emotion_rules, emotion_ml)

        # Hashtag urgent => petit bonus urgence
        if "urgent" in hashtag_words:
            urgency_rule += 0.02  # petit boost
        urgency_final = _clamp01(urgency_rule)

        authority_final = _clamp01(authority_rule)
        social_proof_final = _clamp01(social_proof_rule)

        return {
            "structural_features": {
                "avg_sentence_len": round(_safe_div(total_words, total_sentences), 2),
                "lexical_diversity": round(_safe_div(unique_words, total_words), 2),
                "exclam_density": round(_safe_div(exclam_count, total_sentences), 2),
                "question_density": round(_safe_div(question_count, total_sentences), 2),
                "caps_ratio": round(caps_ratio, 3),
                "emoji_density": round(_safe_div(emoji_count, total_sentences), 2),
                "hashtag_density": round(_safe_div(hashtag_count, total_sentences), 2)
            },
            "pronominal_markers": {
                "ratio_self": round(_safe_div(word_counts["self"], total_words), 3),
                "ratio_group": round(_safe_div(word_counts["group"], total_words), 3),
                "ratio_other": round(_safe_div(word_counts["other"], total_words), 3)
            },
            "semantic_orientation": {
                "imperative_ratio": round(imperative_ratio, 3),
                "imperative_hits": int(imperative_hits),
                "help_seeking": round(_safe_div(word_counts["help"], total_words), 3),
                "conflict_intensity": round(_safe_div(word_counts["conflict"], total_words), 3),
                "tech_jargon_density": round(_safe_div(tech_hits, total_words), 3),
                "materialism_focus": round(_safe_div(word_counts["money"], total_words), 3),
                "absolutism_ratio": round(_safe_div(word_counts["absolutism"], total_words), 3),
                "hedging_ratio": round(_safe_div(hedging_hits, total_words), 3)
            },
            "cognitive_style": {
                "temporal_focus": temporal_focus,
                "emotion_intensity": round(_clamp01(emotion_final), 3),
                "emotion_rules": round(emotion_rules, 3),
                "emotion_ml": round(_clamp01(emotion_ml), 3)
            },
            "vulnerability_triggers": {
                "urgency_score": round(urgency_final, 3),
                "authority_score": round(authority_final, 3),
                "fear_score": round(_clamp01(fear_final), 3),
                "fear_rule": round(fear_rule, 3),
                "fear_ml": round(_clamp01(fear_ml), 3),
                "social_proof_score": round(social_proof_final, 3),
                "ml_emotions": ml_emotions,
                "synergy": {
                    "auth_urg": 1 if (authority_final >= 0.02 and urgency_final >= 0.02) else 0,
                    "fear_urg": 1 if (_clamp01(fear_final) >= 0.10 and urgency_final >= 0.02) else 0
                }
            }
        }
