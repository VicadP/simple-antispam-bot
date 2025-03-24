from sentence_transformers import SentenceTransformer, SimilarityFunction
import re
import nltk
import emoji
from typing import Union, Optional
from pymorphy3 import MorphAnalyzer
from numpy import ndarray


class TextEncoder:

    def __init__(self, model: str):
        self.encoder = SentenceTransformer(model_name_or_path=model, device="cpu", similarity_fn_name=SimilarityFunction.DOT_PRODUCT)

    @staticmethod
    def clean_text(text: str , stop_words: Optional[Union[list, tuple]] = None, morph_analyzer: Optional[MorphAnalyzer] = None) -> str:
        text = emoji.replace_emoji(text, replace="")
        text = text.lower()
        text = re.sub(r'[^\w\s]', " ", text) # удаляем символы и пунктуацию
        text = re.sub(r'\s+', " ", text)     # удаляем избыточные пробелы
        text = text.strip()
        text = nltk.word_tokenize(text, language="russian")
        if morph_analyzer:
            text = [morph_analyzer.parse(word)[0].normal_form for word in text] # лемматизация (необходима, если исп. TfIdf)
        if stop_words:
            text = [word for word in text if word not in stop_words]
        return " ".join(text)

    def encode(self, message: list[str]) -> ndarray:
        message = list(map(self.clean_text, message))
        return self.encoder.encode(message, 
                                   normalize_embeddings=True, 
                                   show_progress_bar=False, 
                                   convert_to_numpy=True) # dot product на нормализованных эмбедингах == cosine similiarity
    
    def compute_similiarity(self, message: list[str], embeddings: ndarray) -> float:
        return self.encoder.similarity(self.encode(message), embeddings).numpy().max() # можно попробовать брать квантиль или среднее по топ-3/5 для более робастной оценки