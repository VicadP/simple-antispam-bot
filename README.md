# Описание

Телеграм-бот предназначен для автоматического обнаружения спам-сообщений в чатах. Бот анализирует входящие сообщения с помощью методов машинного обучения и лингвистического анализа.

## Основные фунции бота

1. Анализ эмоджи:
    * Измеряет долю эмоджи в сообщении
    * Определяет сообщения с подозрительно высоким содержанием эмоджи

2. Косинусная близость:
    * Сравнивает текст сообщения с базой известных спам-сообщений
    * Вычисляет меру схожести с помощью векторного представления текста

3. Классификация с помощью LinearSVC:
    * Использует модель машинного обучения Linear SVC
    * Определяет вероятность того, что сообщение является спамом

## Структура репозитория

```
TELEGRAM_ANTISPAM_BOT/
├── bot/
│   ├── config/        # Переменные и настройки
│   ├── core/          # Основные функциональные части бота: классификатор, энкодер и хэндлер
│   ├── data/          # Модули, отвественные за работу с данными, базой данных
│   ├── model/         # Модули, отвественные за оптимизацию, обучение и сохранение классификатора
├── data/              # Данные
├── notebooks/         # Прочие ноутбуки 
├── tests/             # Юнит тесты
├── main.py            # Основной скрипт для запуска бота
```
