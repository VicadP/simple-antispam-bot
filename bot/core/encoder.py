from sentence_transformers import SentenceTransformer, SimilarityFunction
import re
import emoji
from numpy import ndarray

class TextEncoder:

    def __init__(self, model: str):
        self.encoder = SentenceTransformer(model_name_or_path=model, device="cpu", similarity_fn_name=SimilarityFunction.DOT_PRODUCT)

    @staticmethod
    def clean_text(text: str) -> str:
        text = emoji.replace_emoji(text, replace="")
        text = text.lower()
        text = re.sub(r'[^\w\s]', " ", text) # удаляем символы и пунктуацию
        text = re.sub(r'\s+', " ", text)     # удаляем избыточные пробелы
        text = text.strip()
        text = text.split()                  # токенизируем, если дальше хотим делать лемматизацию и удаление стоп слов (сейчас не применяется)
        return " ".join(text)

    def encode(self, message: list[str]) -> ndarray:
        message = list(map(self.clean_text, message))
        return self.encoder.encode(
            message, 
            normalize_embeddings=True, 
            show_progress_bar=False, 
            convert_to_numpy=True
        ) # dot product на нормализованных эмбедингах == cosine similiarity
    
    def compute_similiarity(self, message: list[str], embeddings: ndarray) -> float:
        return self.encoder.similarity(
            self.encode(message), 
            embeddings
        ).numpy().max() # можно попробовать брать квантиль или среднее по топ-3/5 для более устойчивой оценки