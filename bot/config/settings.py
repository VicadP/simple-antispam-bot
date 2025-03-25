from pathlib import Path

class Settings:
    TELEGRAM_TOKEN: str = ""
    BOT_MODE: str = "soft"
    ROOT_PATH: Path = Path().cwd()
    DB_PATH: Path = ROOT_PATH / "data/embeddings.sqlite3"
    CLF_PATH: Path = ROOT_PATH / "bot/core/classifier.joblib"
    DATA_PATH: Path = ROOT_PATH / "data/data.csv"
    MODEL_CLS: str = "sergeyzh/rubert-tiny-turbo"            # по результатам калибровки лучшая модель в соотношение производительность-размер (можно попробовать более тяжелые модели)
    MODEL_STS: str = "paraphrase-multilingual-MiniLM-L12-v2" # по результатам калибровки модель более точная в измерении схожести чем rubert*
    RNG_INT: int = 42
    PROBA_TRHLD: float = 0.6
    SIMILIARITY_TRHLD: float = 0.90                          # чем выше, тем меньше fpr. При смене модели нужно перекалибровывать порог
    EMOJI_TRHLD: float = 0.35
    WHITELIST: list = [
        
    ]  

class Queries:
    CREATE_TABLE: str =  """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            embedding BLOB
        );
    """
    INSERT: str = """
        INSERT INTO documents (message, embedding)
        VALUES (?, ?);
    """
    DELETE_ENT: str = """
        DELETE FROM documents;
    """
    DELETE_SEQ: str = """
        DELETE FROM sqlite_sequence WHERE name='documents';
    """
    SELECT: str = """
        SELECT embedding FROM documents;
    """

COL_MESSAGE = "message"
COL_TARGET = "label"