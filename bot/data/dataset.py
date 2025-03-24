from bot.config.settings import *
import pandas as pd
from numpy import ndarray

class DatasetManager:

    def __init__(self, path=Settings.DATA_PATH):
        self.data = pd.read_csv(path, sep=";", encoding="utf-8")
        self.data = self.data.drop_duplicates()

    def get_spam_messages(self) -> ndarray:
        return self.data.query("label == 1")[COL_MESSAGE].copy(deep=True).to_numpy()

    def get_ham_messages(self) -> ndarray:
        return self.data.query("label == 0")[COL_MESSAGE].copy(deep=True).to_numpy()

    def get_data(self) -> pd.DataFrame:
        return self.data.copy(deep=True)
    
    def get_X(self) -> pd.Series:
        return self.data[COL_MESSAGE].copy(deep=True)
    
    def get_y(self) -> pd.Series:
        return self.data[COL_TARGET].copy(deep=True)