import sqlite3
import logging
from bot.config.settings import Settings
from typing import Optional

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("db_logger")

class DatabaseManager:

    def __init__(self, db_schema: str = Settings.DB_PATH):
        self.db_schema = db_schema

    def create_table(self, query: str):
        try:
            con = sqlite3.connect(self.db_schema)
            cursor = con.cursor()
            cursor.execute(query)
            con.commit()
            logger.info("Таблица успешно создана")
        except Exception as err:
            logger.info(f"Ошибка в запросе: {query}\n Error: {err}")
        finally:
            con.close()
        
    def insert_one(self, query: str, row: list):
        try:
            con = sqlite3.connect(self.db_schema)
            cursor = con.cursor()
            cursor.execute(query, row)
            con.commit()
            logger.info("Строка успешно добавлена")
        except Exception as err:
            logger.info(f"Ошибка в запросе: {query}\n Error: {err}")
        finally:
            con.close()

    def insert_many(self, query: str, rows: list[tuple]):
        try:
            con = sqlite3.connect(self.db_schema)
            cursor = con.cursor()
            cursor.executemany(query, rows)
            con.commit()
            logger.info("Строки успешно добавлены")
        except Exception as err:
            logger.info(f"Ошибка в запросе: {query}\n Error: {err}")
        finally:
            con.close() 

    def delete_all(self, query_table: str, query_sequence: Optional[str] = None):
        try:
            con = sqlite3.connect(self.db_schema)
            cursor = con.cursor()
            cursor.execute(query_table)
            if query_sequence:
                cursor.execute(query_sequence)
            con.commit()
            if query_sequence:
                logger.info("Строки и sequence успешно удалены")
            else:
                logger.info("Строки успешно удалены")
        except Exception as err:
            logger.info(f"Ошибка в запросе: {query_table}\n Error: {err}")
        finally:
            con.close()              

    def select_all(self, query: str) -> list[tuple]:
        try:
            con = sqlite3.connect(self.db_schema)
            cursor = con.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return rows
        except Exception as err:
            logger.info(f"Ошибка в запросе: {query}\n Error: {err}")
        finally:
            con.close()