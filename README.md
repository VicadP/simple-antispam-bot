# Описание

Телеграм-бот предназначен для автоматического обнаружения спам-сообщений. \
Бот анализирует входящие сообщения и с помощью методов машинного обучения и лингвистического анализа определяет является ли сообщение спамом. \
В зависимости от режима, бот предпринимает действие:

- если режим `soft`, то бот удалит спам сообщение
- если режим `hard`, то удалит спам сообщение и забанит пользователя

Бот автоматически удаляет все команды и свои ответы на команды, отправленные в чат, c задержкой в $x$ секунд, чтобы не нагружать чат и не создавать флуд.

В качестве модели для построения эмбедингов используется [`rubert-tiny-turbo`](https://huggingface.co/sergeyzh/rubert-tiny-turbo) из [`sentence_transformers`](https://sbert.net/#). \
В качестве классификатора используется [`LinearSVC`](https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html). Выбор данного классификатора основан на оценке кросс-валидации (сравнивалось три модели: `GaussianNB`, `Logistic Regression`, `LinearSVC`).

Текущий классификатор обучен на небольшой выборке, состоящей из $500+$ наблюдений, с распределением классов $\approx 60/40$

## Логика сканирования сообщений

Бот сканирует все текстовые сообщения, за исключением команд, и осуществляет следующий набор проверок до первого срабатывания:

1. Проверка на длину сообщения - сообщения короче 15 символов бот не проверяет. \
Данная проверка требуется, чтобы исключить FP на коротких сообщений. Пороговое значение было подобрано на основании анализа длины спам сообщений.
2. Проверка на whitelist - бот не проверяет сообщения пользователей из whitelist.
3. Проверка на эмодзи - если доля эмодзи выше 35%, то бот считает такое сообщение спамом. Порог был подобран исходя из того, что многие эмодзи являются кастомными и не считаются библиотекой [`emoji`](https://pypi.org/project/emoji/).
4. Оценка $P(y = спам | x)$ - если вероятность принадлежности к спаму выше 65% процентов, то бот считает такое сообщение спамом.
5. Оценка косинусной близости эмбедингов - если метрика выше 95%, то бот считает такое сообщение спамом.

Все пороговые значения являются свободными переменными и могут быть изменены, исходя из нужд.

## Дообучение и пересчет эмбедингов

Для того, чтобы дообучить модель достаточно запустить `./bot/model/optimize.py` и после запустить `./bot/model/train.py` с найденными параметрами. \
Для пересчета эмбедингов достаточно запустить `./bot/data/load_embeddings.py`

## Основные команды

1. `/help` - выводит информацию о боте и основных командах
2. `/spam` - позволяет в ручном режиме удалить спам сообщение и автоматически добавить его в обучающую выборку с лейблом **спам**. Для этого необходимо ответить на спам сообщение с использование данной команды. Не рекомендуется добавлять сообщения GPT ботов, так как они мимикрируют под не спам сообщения и могут существенно снизить качество классификатора.
3. `/mode` - позволяет менять режим бота с `soft` на `hard`. Команда доступна только для админов.
4. `/whitelist` - позволяет добавлять/удалять пользоватей в/из whitelist по их id. Бот хранит информацию о whitelist для каждого чата. При перезагрузке бота данные о whitelist не будет потеряны. Для того, чтобы получить id пользователя трубется воспользоваться функционалом бота `@username_to_id_bot`. Команда доступна только для админов.

## Структура репозитория

```
TELEGRAM_ANTISPAM_BOT/
├── bot/
│   ├── config/             # Переменные, пороговые значения и прочие настройки
│   ├── core/               # Основные функциональные части бота: классификатор, энкодер и хэндлер
│   ├── data/               # Модули, отвественные за работу с данными, базой данных
│   ├── model/              # Модули, отвественные за оптимизацию, обучение и сохранение классификатора
├── data/                   # Данные
├── notebooks/              # Ноутбуки 
├── tests/                  # Юнит тесты (сейчас отсуствуют)
├── main.py                 # Основной скрипт для запуска бота
├── requirements_core.txt   # Основыне зависимости, требуемые для работы бота
├── etc
```
