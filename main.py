import telebot
import sqlite3 as sql
from datetime import datetime
import random
import requests
import os
from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
NUTRITIONIX_APP_KEY = os.getenv("NUTRITIONIX_APP_KEY")
FOOD_EMOJIS = list(
    "🍇🍈🍉🍊🍋🍋‍🟩🍌🍍🥭🍎🍏🍐🍑🍒🍓🫐🥝🍅🫒🥥🥑🍆🥔🥕🌽🌶️🫑🥒🥬🥦🧄🧅🥜🫘🌰🫚🫛🍄‍🟫🍞🥐🥖🫓🥨🥯🥞🧇🧀🍖🍗🥩🥓🍔🍟🍕🌭🥪🌮🌯🫔🥙🧆🥚🍳🥘🍲🫕🥣🥗🍿🧈🧂🥫🍝🍱🍘🍙🍚🍛🍜🍠🍢🍣🍤🍥🥮🍡🥟🥠🥡🍦🍧🍨🍩🍪🎂🍰🧁🥧🍫🍬🍭🍮🍯🍼🥛☕🫖🍵🍶🍾🍷🍸🍹🍺🍻🥂🥃🫗🥤🧋🧃🧉🥢🍽️🍴🥄🔪🫙🏺"
)

bot = telebot.TeleBot(BOT_TOKEN)

con = sql.connect("meals.db")
c = con.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS meals
             (time text, meal text, amount integer, calories integer)""")
con.commit()
con.close()

print("bot started")


def get_nutrition_info(query):
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_APP_KEY,
    }
    payload = {"query": query}
    response = requests.post(
        "https://trackapi.nutritionix.com/v2/natural/nutrients",
        headers=headers,
        json=payload,
    )
    response.raise_for_status()
    return response.json()


@bot.message_handler(commands=["add_meal"])
def add_meal(message: telebot.types.Message):
    try:
        _, meal_info = message.text.split(maxsplit=1)
        meal, amount = meal_info.rsplit(maxsplit=1)
        amount = int(amount)

        data = get_nutrition_info(meal)
        food_info = data["foods"][0]
        calories_per_100g = (
            int(food_info["nf_calories"])
            / int(food_info.get("serving_weight_grams", 100))
            * 100
        )
        total_calories = calories_per_100g * amount / 100

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con = sql.connect("meals.db")
        c = con.cursor()
        c.execute(
            "INSERT INTO meals VALUES (?, ?, ?, ?)",
            (current_time, meal, amount, total_calories),
        )

        bot.send_message(
            message.chat.id, f"{random.choice(FOOD_EMOJIS)} Блюдо успешно добавлено!"
        )

        con.commit()
        con.close()
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат. Используй: /add_meal {блюдо} {граммы}.",
        )
    except requests.exceptions.RequestException as e:
        bot.send_message(
            message.chat.id,
            f"❌ Что-то пошло не так! Возможно, вы ввели еду не на английском.\n\n`{e}`",
            parse_mode="Markdown",
        )
    except (KeyError, IndexError):
        bot.send_message(message.chat.id, "❌ К сожалению такой еды нет у нас в базе!")


@bot.message_handler(commands=["view_meals"])
def view_meals(message):
    con = sql.connect("meals.db")
    c = con.cursor()
    c.execute("SELECT * FROM meals")
    meals = c.fetchall()
    con.commit()
    con.close()
    if meals:
        meal_list = "\n".join(
            [
                f"{time} - {meal} ({amount}g) - {calories:.2f} cal"
                for time, meal, amount, calories in meals
            ]
        )
        bot.send_message(
            message.chat.id,
            f"{random.choice(FOOD_EMOJIS)} Вот Ваши блюда:\n{meal_list}",
        )
    else:
        bot.send_message(message.chat.id, "❌ Вы пока что не добавляли никакой еды!")


bot.infinity_polling()
