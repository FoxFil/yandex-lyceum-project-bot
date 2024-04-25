import telebot
import sqlite3 as sql
from datetime import datetime, timedelta
import random
import requests
import os
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt

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
             (id integer, time text, meal text, amount integer, calories integer, protein integer, fat integer, carbs integer)""")
con.commit()
con.close()

print("bot started")


@bot.message_handler(commands=["start"])
def start(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я помогу тебе следить за питанием.\n\n"
        "Введи /help для получения списка команд.",
    )


@bot.message_handler(commands=["help"])
def help(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        """Список команд:
/add {блюдо} {граммы} - добавить блюдо.
/view [day, week, month, year, all] - посмотреть список блюд за определенный период.
/start - начать работу с ботом.
/help - список команд.""",
    )


def get_nutrition_info(query, api_id=NUTRITIONIX_APP_ID, api_key=NUTRITIONIX_APP_KEY):
    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        "x-app-id": api_id,
        "x-app-key": api_key,
        "Content-Type": "application/json",
    }
    data = {"query": query}
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        data = response.json()
        foods = data["foods"]
        if foods:
            food = foods[0]
            return {
                "calories": food["nf_calories"],
                "protein": food["nf_protein"],
                "fat": food["nf_total_fat"],
                "carbs": food["nf_total_carbohydrate"],
            }
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


@bot.message_handler(commands=["add"])
def add(message: telebot.types.Message):
    try:
        _, meal_info = message.text.split(maxsplit=1)
        meal, amount = meal_info.rsplit(maxsplit=1)
        amount = int(amount)

        nutrition_info = get_nutrition_info(meal)

        if nutrition_info:
            calories = nutrition_info["calories"]
            protein = nutrition_info["protein"]
            fat = nutrition_info["fat"]
            carbs = nutrition_info["carbs"]

            # Рассчитываем общее количество КБЖУ
            total_calories = calories * amount / 100
            total_protein = protein * amount / 100
            total_fat = fat * amount / 100
            total_carbs = carbs * amount / 100

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            con = sql.connect("meals.db")
            c = con.cursor()

            c.execute(
                "INSERT INTO meals (id, time, meal, amount, calories, protein, fat, carbs) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message.from_user.id,
                    current_time,
                    meal,
                    amount,
                    total_calories,
                    total_protein,
                    total_fat,
                    total_carbs,
                ),
            )

            con.commit()
            con.close()

            bot.send_message(
                message.chat.id,
                f"{random.choice(FOOD_EMOJIS)} Блюдо успешно добавлено!",
            )
        else:
            bot.send_message(message.chat.id, "❌ Информация о КБЖУ не найдена.")

    except Exception as e:
        print(f"Ошибка: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка. Используй формат /add {блюдо} {граммы}",
        )


@bot.message_handler(commands=["view"])
def view(message: telebot.types.Message):
    if len(message.text.split()) == 1:
        period = "day"
    else:
        _, period = message.text.split(maxsplit=1)

    if period == "day":
        today = datetime.now().strftime("%Y-%m-%d")

        con = sql.connect("meals.db")
        c = con.cursor()
        c.execute(
            "SELECT meal, amount, calories, protein, fat, carbs FROM meals WHERE time LIKE ? AND id = ?",
            (f"{today}%", f"{message.from_user.id}"),
        )
        meals = c.fetchall()
        con.close()

        if meals:
            calories_total, protein_total, fat_total, carbs_total = 0, 0, 0, 0
            meal_list = "\n".join(
                [
                    f"- {meal} ({amount}g): *{calories:.2f} kcal, {protein:.2f}g P, {fat:.2f}g F, {carbs:.2f}g C*"
                    for meal, amount, calories, protein, fat, carbs in meals
                ]
            )
            for _, _, calories, protein, fat, carbs in meals:
                calories_total += calories
                protein_total += protein
                fat_total += fat
                carbs_total += carbs

            bot.send_message(
                message.chat.id,
                f"""{random.choice(FOOD_EMOJIS)} *Вот ваши сегодняшние блюда*:\n\n{meal_list}\n\n📝 В сумме: *{calories_total:.2f} kcal, {protein_total:.2f}g P, {fat_total:.2f}g F, {carbs_total:.2f}g C* за день""",
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
                "SELECT calories, protein, fat, carbs, strftime('%Y-%m-%d', time) as date FROM meals WHERE time >= ? AND id = ?",
                (start_date, f"{message.from_user.id}"),
            )

            calories_by_date = {}
            protein_by_date = {}
            fat_by_date = {}
            carbs_by_date = {}
            for calories, protein, fat, carbs, date in data.fetchall():
                calories_by_date.setdefault(date, []).append(calories)
                protein_by_date.setdefault(date, []).append(protein)
                fat_by_date.setdefault(date, []).append(fat)
                carbs_by_date.setdefault(date, []).append(carbs)
            con.commit()
            con.close()

            total_days = len(calories_by_date)
            avg_calories = (
                sum(sum(daily_calories) for daily_calories in calories_by_date.values())
                / total_days
            )
            avg_protein = (
                sum(sum(daily_protein) for daily_protein in protein_by_date.values())
                / total_days
            )
            avg_fat = (
                sum(sum(daily_fat) for daily_fat in fat_by_date.values()) / total_days
            )
            avg_carbs = (
                sum(sum(daily_carbs) for daily_carbs in carbs_by_date.values())
                / total_days
            )
            bot.send_message(
                message.chat.id,
                f"""{random.choice(FOOD_EMOJIS)} Средние показатели за {f'''последний {"месяц" if period == "month" else "год"}''' if period != "week" else "последнюю неделю"}:\n\n*{avg_calories:.2f} kcal* в день.\n*{avg_protein:.2f} граммов протеина* в день.\n*{avg_fat:.2f} граммов жира* в день.\n*{avg_carbs:.2f} граммов углеводов* в день.""",
                parse_mode="Markdown",
            )
        except ZeroDivisionError:
            bot.send_message(message.chat.id, "❌ Не найдено блюд за этот период.")
    elif period == "all":
        con = sql.connect("meals.db")
        c = con.cursor()
        meals = c.execute(
            "SELECT time, meal, amount, calories, protein, fat, carbs FROM meals WHERE id = ?",
            (f"{message.from_user.id}",),
        ).fetchall()
        con.commit()
        con.close()

        if meals:
            df = pd.DataFrame(
                meals,
                columns=[
                    "Time",
                    "Meal",
                    "Grams",
                    "Kcalories",
                    "Protein (gr)",
                    "Fat (gr)",
                    "Carbs (gr)",
                ],
            )
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


@bot.message_handler(commands=["graph"])
def generate_calorie_graph(message):
    if len(message.text.split()) == 1:
        period = "day"
    else:
        _, period = message.text.split(maxsplit=1)

    try:
        if period == "day":
            today = datetime.now().strftime("%Y-%m-%d")
            con = sql.connect("meals.db")
            c = con.cursor()
            c.execute(
                "SELECT time, calories, protein, fat, carbs FROM meals WHERE time LIKE ? AND id = ?",
                (f"{today}%", f"{message.from_user.id}"),
            )
            meals = c.fetchall()
            con.commit()
            con.close()

            times = [
                datetime.strptime(time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
                for time, _, _, _, _ in meals
            ]
            calories = [cal for _, cal, _, _, _ in meals]
            protein = [protein for _, _, protein, _, _ in meals]
            fat = [fat for _, _, _, fat, _ in meals]
            carbs = [carbs for _, _, _, _, carbs in meals]

            width = 0.2
            x = range(len(times))

            plt.bar(x, calories, width, label="Calories")
            plt.bar([p + width for p in x], protein, width, label="Protein")
            plt.bar([p + width * 2 for p in x], fat, width, label="Fat")
            plt.bar([p + width * 3 for p in x], carbs, width, label="Carbs")

            plt.xlabel("Время")
            plt.ylabel("Граммы")
            plt.title("КБЖУ потреблено за сегодня")
            plt.xticks([p + width * 1.5 for p in x], times, rotation=45, ha="right")
            plt.legend()

        elif period in ("week", "month", "year"):
            try:
                if period == "week":
                    start_date = (datetime.now() - timedelta(days=7)).strftime(
                        "%Y-%m-%d"
                    )
                elif period == "month":
                    start_date = (datetime.now() - timedelta(days=30)).strftime(
                        "%Y-%m-%d"
                    )
                elif period == "year":
                    start_date = (datetime.now() - timedelta(days=365)).strftime(
                        "%Y-%m-%d"
                    )
                con = sql.connect("meals.db")
                c = con.cursor()
                data = c.execute(
                    "SELECT calories, protein, fat, carbs, strftime('%Y-%m-%d', time) as date FROM meals WHERE time >= ? AND id = ?",
                    (start_date, f"{message.from_user.id}"),
                )

                calories_by_date = {}
                protein_by_date = {}
                fat_by_date = {}
                carbs_by_date = {}
                for calories, protein, fat, carbs, date in data.fetchall():
                    calories_by_date.setdefault(date, []).append(calories)
                    protein_by_date.setdefault(date, []).append(protein)
                    fat_by_date.setdefault(date, []).append(fat)
                    carbs_by_date.setdefault(date, []).append(carbs)
                con.commit()
                con.close()

                total_days = len(calories_by_date)
                avg_calories = (
                    sum(
                        sum(daily_calories)
                        for daily_calories in calories_by_date.values()
                    )
                    / total_days
                )
                avg_protein = (
                    sum(
                        sum(daily_protein) for daily_protein in protein_by_date.values()
                    )
                    / total_days
                )
                avg_fat = (
                    sum(sum(daily_fat) for daily_fat in fat_by_date.values())
                    / total_days
                )
                avg_carbs = (
                    sum(sum(daily_carbs) for daily_carbs in carbs_by_date.values())
                    / total_days
                )

                dates = list(calories_by_date.keys())
                width = 0.2
                x = range(len(dates))

                plt.bar(x, avg_calories, width, label="Kcalories")
                plt.bar([p + width for p in x], avg_protein, width, label="Protein")
                plt.bar([p + width * 2 for p in x], avg_fat, width, label="Fat")
                plt.bar([p + width * 3 for p in x], avg_carbs, width, label="Carbs")

                plt.xlabel("Дата")
                plt.ylabel("Среднее (g)")
                plt.title(
                    f"""Средее КБЖУ за {f'''последний {"месяц" if period == "month" else "год"}''' if period != "week" else "последнюю неделю"}"""
                )
                plt.xticks([p + width * 1.5 for p in x], dates, rotation=45, ha="right")
                plt.legend()

            except ZeroDivisionError:
                bot.send_message(message.chat.id, "❌ Не найдено блюд за этот период.")
        else:
            bot.send_message(
                message.chat.id,
                "❌ Неверный период. Используйте: day, week, month, year",
            )
            return

        plt.tight_layout()
        plt.savefig("calories_graph.png")
        plt.close()

        with open("calories_graph.png", "rb") as f:
            bot.send_photo(message.chat.id, f)
        os.remove("calories_graph.png")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")


bot.infinity_polling()
