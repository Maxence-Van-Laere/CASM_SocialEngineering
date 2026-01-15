from transformers import pipeline

class EmotionHF:
    def __init__(self, model_name="ayoubkirouane/BERT-Emotions-Classifier"):
        self.clf = pipeline("text-classification", model=model_name, top_k=None)

    def scores(self, text: str) -> dict:
        # returns list of {label, score}
        res = self.clf(text)[0]
        out = {r["label"].lower(): float(r["score"]) for r in res}
        return out
