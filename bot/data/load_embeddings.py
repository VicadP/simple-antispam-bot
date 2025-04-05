from bot.config.settings import Settings, Queries
from bot.core.encoder import TextEncoder
from bot.data.database import DatabaseManager
from bot.data.dataset import DatasetManager
import pickle
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("embedding_loader")

RELOAD_TABLE = 1 # оставляем 1, кроме самой первой загрузки

def run_loading():
    try:
        encoder = TextEncoder(Settings.MODEL_CLS)
        dm = DatasetManager()
        db = DatabaseManager()

        messages = dm.get_spam_messages()
        db.create_table(Queries.CREATE_TABLE)
        if RELOAD_TABLE == 1:
            db.delete_all(Queries.DELETE_ENT, Queries.DELETE_SEQ)
        embeddings = encoder.encode(messages)
        rows = [(message, pickle.dumps(embedding)) 
                for message, embedding in zip(messages, embeddings)]
        db.insert_many(Queries.INSERT, rows)
        logger.info(f"Строки успешно загружены. Строк загружено: {len(db.select_all(Queries.SELECT))}")
    except Exception as e:
        logger.error(f"Ошибка при создании и сохранении эмбедингов\n{e}")

if __name__ == "__main__":
    run_loading()


