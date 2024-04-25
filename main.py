import telebot
import sqlite3 as sql
from datetime import datetime, timedelta
import random
import requests
import os
from dotenv import load_dotenv
import pandas as pd
import matplotlib

matplotlib.use('Agg')  # Установить backend_agg
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
NUTRITIONIX_APP_KEY = os.getenv("NUTRITIONIX_APP_KEY")
FOOD_EMOJIS = list(
    "🍇🍈🍉🍊🍋🍋‍🟩🍌🍍🥭🍎🍏🍐🍑🍒🍓🫐🥝🍅🫒🥥🥑🍆🥔🥕🌽🌶🫑🥒🥬🥦🧄🧅🥜🫘🌰🫚🫛🍄‍🟫🍞🥐🥖🫓🥨🥯🥞🧇🧀🍖🍗🥩🥓🍔🍟🍕🌭🥪🌮🌯🫔🥙🧆🥚🍳🥘🍲🫕🥣🥗🍿🧈🧂🥫🍝🍱🍘🍙🍚🍛🍜🍠🍢🍣🍤🍥🥮🍡🥟🥠🥡🍦🍧🍨🍩🍪🎂🍰🧁🥧🍫🍬🍭🍮🍯🍼🥛☕️🫖🍵🍶🍾🍷🍸🍹🍺🍻🥂🥃🫗🥤🧋🧃🧉🥢🍽🍴🥄🔪🫙🏺"
)

bot = telebot.TeleBot(BOT_TOKEN)

# Создаем или подключаемся к базе данных и создаем таблицу, если она не существует
con = sql.connect("meals.db")
c = con.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS meals
             (id integer, time text, meal text, amount integer, 
              calories integer, protein, fat, carbs)""")
con.commit()
con.close()

print("bot started")


@bot.message_handler(commands=["start"])
def start(message: telebot.types.Message):
    bot.send_message(message.chat.id, "Привет! Я помогу тебе следить за питанием.\n"
                                      "Введи /help для получения списка команд.")


@bot.message_handler(commands=["help"])
def help(message: telebot.types.Message):
    bot.send_message(message.chat.id, """Список команд:
/add_meal {блюдо} {граммы} - добавить блюдо
/view_meals [day, week, month, year, all] - посмотреть список блюд за определенный период 
/start - начать работу с ботом
/help - список команд""")


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


@bot.message_handler(commands=["add_meal"])
def add_meal(message: telebot.types.Message):
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
                    message.from_user.id, current_time, meal, amount, total_calories, total_protein, total_fat,
                    total_carbs)
            )

            con.commit()
            con.close()

            bot.send_message(
                message.chat.id, f"{random.choice(FOOD_EMOJIS)} Блюдо успешно добавлено!"
            )
        else:
            bot.send_message(message.chat.id, "Информация о КБЖУ не найдена.")

    except Exception as e:
        print(f"Ошибка: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте еще раз.")


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


@bot.message_handler(commands=["graph"])
def send_calories_graph(message: telebot.types.Message):
    user_id = message.from_user.id
    period = "week"  # По умолчанию строим график за неделю

    try:
        con = sql.connect("meals.db")
        df = pd.read_sql_query(f"SELECT time, calories FROM meals WHERE id = {user_id}", con)
        con.close()

        df['time'] = pd.to_datetime(df['time'])

        df_daily = df.groupby(df['time'])['calories'].sum().reset_index()

        if period == "week":
            start_date = (datetime.now() - timedelta(days=6)).date()
            df_daily = df_daily[df_daily['time'].dt.date >= start_date]  # Добавить .dt.date
        elif period == "month":
            start_date = datetime.now() - timedelta(days=29)
            df_daily = df_daily[df_daily['time'].dt.date >= start_date]  # Добавить .dt.date

        # Строим график
        plt.figure(figsize=(10, 5))
        plt.plot(df_daily['time'], df_daily['calories'])
        plt.xlabel("Дата")
        plt.ylabel("Калории (ккал)")
        plt.title("Потребление калорий")
        plt.grid(True)

        # Формат даты - день-месяц
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))

        # Сохраняем график в файл
        plot_path = "plot.png"
        plt.savefig(plot_path)

        # Отправляем график пользователю
        with open(plot_path, "rb") as f:
            bot.send_photo(message.chat.id, f)

        # Удаляем файл с графиком
        os.remove(plot_path)

    except Exception as e:
        print(f"Ошибка: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка при построении графика.")


bot.infinity_polling()
