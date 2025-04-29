from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import html
import os

app = Flask(__name__)

def clean_text(text):
    soup = BeautifulSoup(text, 'html.parser')
    for sup in soup.find_all('sup'):
        sup.decompose()
    for sep in soup.find_all('span', class_='seperator'):
        sep.replace_with(' oder ')
    clean = soup.get_text().replace('+', '').strip()
    return html.unescape(clean)

def get_available_days(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
    available_days = []
    for headline in soup.find_all('h3', class_=['default-headline', 'active-headline']):
        text = headline.get_text(strip=True)
        try:
            date_part = text.split(',')[1].strip()
            available_days.append(date_part)
        except IndexError:
            continue
    return available_days

def get_mensa_filtered(url, date):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')

    weekday = date.strftime('%A')
    weekday_map = {
        'Monday': 'Montag',
        'Tuesday': 'Dienstag',
        'Wednesday': 'Mittwoch',
        'Thursday': 'Donnerstag',
        'Friday': 'Freitag',
        'Saturday': 'Samstag',
        'Sunday': 'Sonntag'
    }
    german_weekday = weekday_map.get(weekday)
    date_str = date.strftime('%d.%m.%Y')

    menu_divs = soup.find_all('div', class_='preventBreak')
    results = {"gerichte": [], "beilagen": []}

    for div in menu_divs:
        headline = div.find('h3', class_=['default-headline', 'active-headline'])
        if headline:
            headline_text = headline.get_text(separator=" ", strip=True)

            if german_weekday in headline_text and date_str in headline_text:
                menu_items = div.select('table.menues tr')
                for item in menu_items:
                    category = item.find('span', class_='menue-category')
                    description_wrapper = item.find('span', class_='menue-desc')
                    description = description_wrapper.find('span', class_='expand-nutr') if description_wrapper else None

                    if category and description:
                        category_text = category.get_text(strip=True)
                        is_relevant = category_text in ["Vegetarisch", "Klassiker"] or (german_weekday == "Freitag" and "Tellergericht" in category_text)
                        if is_relevant:
                            desc_clean = clean_text(str(description))
                            results["gerichte"].append(f"{category_text}: {desc_clean}")

                extras = div.select('table.extras span.menue-item.extra.menue-desc')
                for extra in extras:
                    extra_text = clean_text(str(extra))
                    results["beilagen"].append(extra_text)
    return results

@app.route('/mensa', methods=['POST'])
def alexa_webhook():
    alexa_request = request.get_json(force=True)
    try:
        request_type = alexa_request['request']['type']
        url = "https://www.studierendenwerk-aachen.de/speiseplaene/eupenerstrasse-w.html"

        if request_type == 'LaunchRequest':
            return jsonify({
                "version": "1.0",
                "sessionAttributes": {},
                "response": {
                    "outputSpeech": {
                        "type": "PlainText",
                        "text": "Willkommen beim Mensaplaner! Du kannst mich fragen, was es heute oder an einem bestimmten Tag zu essen gibt."
                    },
                    "shouldEndSession": False
                }
            })

        elif request_type == 'IntentRequest':
            intent_name = alexa_request['request']['intent']['name']
            today = datetime.now()
            available_dates = get_available_days(url)

            if intent_name == "GetMensaPlanIntent":
                target_date = today

            elif intent_name == "GetMensaPlanTomorrowIntent":
                target_date = today + timedelta(days=1)

            elif intent_name == "GetMensaPlanByDayIntent":
                weekday_slot = alexa_request['request']['intent']['slots'].get('weekday', {}).get('value')
                if not weekday_slot:
                    return fallback_response("Ich konnte den gewünschten Tag nicht erkennen.")

                weekdays_de = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]
                weekday_map_reverse = {
                    'monday': 'Montag',
                    'tuesday': 'Dienstag',
                    'wednesday': 'Mittwoch',
                    'thursday': 'Donnerstag',
                    'friday': 'Freitag',
                    'saturday': 'Samstag',
                    'sunday': 'Sonntag'
                }
                weekday_slot = weekday_slot.lower()
                try:
                    target_index = weekdays_de.index(weekday_slot)
                except ValueError:
                    return fallback_response("Diesen Tag kenne ich nicht.")

                for i in range(1, 14):
                    candidate = today + timedelta(days=i)
                    if candidate.weekday() == target_index:
                        target_date = candidate
                        break
                else:
                    return fallback_response(f"Ich konnte kein Datum für {weekday_slot} finden.")
            else:
                return fallback_response("Diesen Befehl kenne ich nicht.")

            target_date_str = target_date.strftime('%d.%m.%Y')
            german_day = target_date.strftime('%A')
            is_today = target_date.date() == today.date()
            is_tomorrow = target_date.date() == (today + timedelta(days=1)).date()

            if is_today:
                day_label = "Heute"
            elif is_tomorrow:
                day_label = "Morgen"
            else:
                day_label = weekday_map_reverse.get(german_day.lower(), german_day)

            if target_date_str not in available_dates:
                speech_text = f"{day_label} gibt es leider keine Angaben zur Mensa."
            else:
                essen = get_mensa_filtered(url, target_date)
                if not essen["gerichte"]:
                    speech_text = f"{day_label} gibt es leider keine Angaben zur Mensa."
                else:
                    speech_text = f"{day_label} gibt es: " + ", ".join(essen["gerichte"])
                    if essen["beilagen"]:
                        speech_text += ". Als Beilage: " + " oder ".join(essen["beilagen"])

            return jsonify({
                "version": "1.0",
                "sessionAttributes": {},
                "response": {
                    "outputSpeech": {
                        "type": "PlainText",
                        "text": speech_text
                    },
                    "shouldEndSession": True
                }
            })

        elif request_type == 'SessionEndedRequest':
            return ('', 200)

        else:
            return fallback_response("Entschuldigung, ich verstehe nur Anfragen zur Mensa.")

    except Exception as e:
        print("Fehler:", str(e))
        return fallback_response("Ein Fehler ist aufgetreten. Bitte versuche es später noch einmal.")

def fallback_response(message):
    return jsonify({
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": message
            },
            "shouldEndSession": True
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
