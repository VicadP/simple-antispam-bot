from pathlib import Path

class Settings:
    TELEGRAM_TOKEN: str = ""
    BOT_MODE: str = "soft"
    ROOT_PATH: Path = Path().cwd()
    DB_PATH: Path = ROOT_PATH / "data/embeddings.sqlite3"
    CLF_PATH: Path = ROOT_PATH / "bot/core/classifier.joblib"
    DATA_PATH: Path = ROOT_PATH / "data/data.csv"
    MODEL_CLS: str = "sergeyzh/rubert-tiny-turbo"         
    RNG_INT: int = 42
    LEN_TRHLD: int = 30
    PROBA_TRHLD: float = 0.5
    SIMILIARITY_TRHLD: float = 0.95                        
    EMOJI_TRHLD: float = 0.35

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
HELP_MESSAGE = """ 
**🔍 Основной функционал:**  
1\. Бот автоматически проверяет все **текстовые сообщения** в чате\.  
2\. При обнаружении подозрительного сообщения:  
   \- Пользователь получает ограничение прав и CAPTCHA
   \- На решение даётся **30 секунд**
3\. Если CAPTCHA не пройдена:  
   \- Сообщение удаляется  
   \- Пользователь исключается из чата  
4\. При успешном решении:  
   \- Автоматическое добавление в whitelist 
   \- Дальнейшие сообщения не проверяются  

**⚙️ Команды:**  
▸ `/mark`  
Ручное удаление спама\. Просто ответьте на спам сообщение, используя данную команду\.
⚠️ Не используйте для LLM\-сообщений \- они искусно маскируются\!  

▸ `/whitelist`  
Управление списком исключений \(очистка/удаление пользователей\)
🚨 Только для администраторов
"""