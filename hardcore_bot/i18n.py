MESSAGES = {
    "uk": {
        "welcome": "Вітаю! Я стежу за цінами на популярні товари в Києві й повідомляю про вигідні знижки.",
        "products_header": "Доступні товари для відстеження:",
        "watch_added": "Додано до відстеження: {product}",
        "digest_header": "Найкращі ціни зараз:",
        "status": "Бот працює. Товарів: {products}. Спостережень: {observations}.",
        "alert_drop": "🔥 Ціна впала на {drop:.0f}%: {product} — {price:.2f} грн у {retailer}",
        "alert_best": "💚 Найкраща ціна сьогодні: {product} — {price:.2f} грн у {retailer}",
        "alert_threshold": "🎯 Нижче вашого порогу: {product} — {price:.2f} грн у {retailer}",
        "unknown_product": "Не знаю такий product_id. Перевірте /products.",
        "language_set": "Мову змінено на українську.",
    },
    "ru": {
        "welcome": "Привет! Я слежу за ценами на популярные товары в Киеве и сообщаю о выгодных скидках.",
        "products_header": "Доступные товары для отслеживания:",
        "watch_added": "Добавлено в отслеживание: {product}",
        "digest_header": "Лучшие цены сейчас:",
        "status": "Бот работает. Товаров: {products}. Наблюдений: {observations}.",
        "alert_drop": "🔥 Цена упала на {drop:.0f}%: {product} — {price:.2f} грн в {retailer}",
        "alert_best": "💚 Лучшая цена сегодня: {product} — {price:.2f} грн в {retailer}",
        "alert_threshold": "🎯 Ниже вашего порога: {product} — {price:.2f} грн в {retailer}",
        "unknown_product": "Не знаю такой product_id. Проверьте /products.",
        "language_set": "Язык изменён на русский.",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "ru" if lang == "ru" else "uk"


def t(key: str, lang: str = "uk", **kwargs) -> str:
    lang = normalize_lang(lang)
    template = MESSAGES[lang][key]
    return template.format(**kwargs)
