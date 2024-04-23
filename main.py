import telebot
import sqlite3 as sql
from datetime import datetime, timedelta
import random
import requests
import os
from dotenv import load_dotenv
import pandas as pd

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
    except requests.exceptions.RequestException:
        bot.send_message(
            message.chat.id,
            "❌ Что-то пошло не так! Возможно, вы ввели еду не на английском, либо такой еды нет.",
            parse_mode="Markdown",
        )
    except (KeyError, IndexError):
        bot.send_message(message.chat.id, "❌ К сожалению такой еды нет у нас в базе!")


@bot.message_handler(commands=["view_meals"])
def view_meals(message: telebot.types.Message):
    if len(message.text.split()) == 1:
        period = "day"
    else:
        _, period = message.text.split(maxsplit=1)
    if period == "day":
        today = datetime.now().strftime("%Y-%m-%d")

        con = sql.connect("meals.db")
        c = con.cursor()
        c.execute(
            "SELECT meal, amount, calories FROM meals WHERE time LIKE ?", (f"{today}%",)
        )
        meals = c.fetchall()
        con.commit()
        con.close()

        if meals:
            calories_total = [cal for _, _, cal in meals]
            meal_list = "\n".join(
                [
                    f"- {meal} ({amount}g): *{calories:.2f} kcal*"
                    for meal, amount, calories in meals
                ]
            )
            bot.send_message(
                message.chat.id,
                f"{random.choice(FOOD_EMOJIS)} *Вот ваши сегодняшние блюда*:\n\n{meal_list}\n\n📝 В сумме: *{sum(calories_total):.2f} kcal* за день",
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                message.chat.id, "❌ Вы пока что не добавляли никакой еды за сегодня!"
            )
    elif period in ("week", "month", "year"):
        try:
            if period == "week":
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            elif period == "month":
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            elif period == "year":
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

            con = sql.connect("meals.db")
            c = con.cursor()
            data = c.execute(
                "SELECT calories, strftime('%Y-%m-%d', time) as date FROM meals WHERE time >= ?",
                (start_date,),
            )
            calories_by_date = {}
            for calories, date in data.fetchall():
                calories_by_date.setdefault(date, []).append(calories)
            con.commit()
            con.close()

            total_days = len(calories_by_date)
            avg_calories = (
                sum(sum(daily_calories) for daily_calories in calories_by_date.values())
                / total_days
            )

            bot.send_message(
                message.chat.id,
                f"""{random.choice(FOOD_EMOJIS)} Средий показатель килокалорий за {f'''последний {"месяц" if period == "month" else "год"}''' if period != "week" else "последнюю неделю"}:\n\n*{avg_calories:.2f} kcal* в день.""",
                parse_mode="Markdown",
            )

        except ZeroDivisionError:
            bot.send_message(message.chat.id, "❌ Не найдено блюд за этот период.")
    elif period == "all":
        con = sql.connect("meals.db")
        c = con.cursor()
        c.execute("SELECT * FROM meals")
        meals = c.fetchall()
        con.commit()
        con.close()

        if meals:
            df = pd.DataFrame(meals, columns=["Time", "Meal", "Grams", "Kcalories"])
            file_path = "meals_data.csv"
            df.to_csv(file_path, index=False)
            with open(file_path, "rb") as f:
                bot.send_document(message.chat.id, f)
            os.remove(file_path)
        else:
            bot.send_message(message.chat.id, "❌ Никаких данных по еде не найдено.")
    else:
        bot.send_message(
            message.chat.id,
            "❌ Неверный период. Используй: day, week, month, year, или all",
        )


bot.infinity_polling()
