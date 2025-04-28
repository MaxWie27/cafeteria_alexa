from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import html
import os

app = Flask(__name__)

def clean_text(text):
    text = text.split('<sup')[0]
    text = text.replace('<span class="seperator">oder</span>', ' oder ')
    text = BeautifulSoup(text, 'html.parser').get_text()
    text = text.replace('+', '').strip()
    text = html.unescape(text)
    return text

def get_mensa_today_filtered(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')

    date = datetime.now()
    weekday_german = date.strftime('%A')
    weekday_map = {
        'Monday': 'Montag',
        'Tuesday': 'Dienstag',
        'Wednesday': 'Mittwoch',
        'Thursday': 'Donnerstag',
        'Friday': 'Freitag',
        'Saturday': 'Samstag',
        'Sunday': 'Sonntag'
    }
    weekday = weekday_map.get(weekday_german)
    date_str = date.strftime('%d.%m.%Y')

    menu_divs = soup.find_all('div', class_='preventBreak')
    results = {"gerichte": [], "beilagen": []}

    for div in menu_divs:
        headline = div.find('h3', class_=['default-headline', 'active-headline'])
        if headline:
            headline_text = headline.get_text(separator=" ", strip=True)

            if weekday in headline_text and date_str in headline_text:
                menu_items = div.select('table.menues tr')
                for item in menu_items:
                    category = item.find('span', class_='menue-category')
                    description_wrapper = item.find('span', class_='menue-desc')
                    description = description_wrapper.find('span', class_='expand-nutr') if description_wrapper else None

                    if category and description:
                        category_text = category.get_text(strip=True)

                        is_relevant = False
                        if category_text == "Vegetarisch" or category_text == "Klassiker":
                            is_relevant = True
                        if weekday == "Freitag" and "Tellergericht" in category_text:
                            is_relevant = True

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

    if alexa_request['request']['type'] == 'LaunchRequest':
        speech_text = "<speak>Willkommen beim Mensaplaner!<break time='0.5s'/>Frag mich, was es heute zu essen gibt.</speak>"

        alexa_response = {
            "version": "1.0",
            "sessionAttributes": {},  # <-- hinzugefügt!
            "response": {
                "outputSpeech": {
                    "type": "SSML",
                    "ssml": speech_text
                },
                "shouldEndSession": False
            }
        }
        return jsonify(alexa_response)

    elif alexa_request['request']['type'] == 'IntentRequest':
        intent_name = alexa_request['request']['intent']['name']

        if intent_name == "GetMensaPlanIntent":
            url = "https://www.studierendenwerk-aachen.de/speiseplaene/eupenerstrasse-w.html"
            essen = get_mensa_today_filtered(url)

            if not essen["gerichte"]:
                speech_text = "<speak>Heute gibt es leider keine Angaben zur Mensa.</speak>"
            else:
                speech_text = "<speak>Heute gibt es:<break time='0.5s'/>"
                speech_text += "<break time='0.5s'/>".join(essen["gerichte"])
                if essen["beilagen"]:
                    speech_text += ". Als Beilage: <break time='0.5s'/>" + " oder ".join(essen["beilagen"])
                speech_text += "</speak>"

        else:
            speech_text = "<speak>Entschuldigung, diesen Befehl kenne ich nicht.<break time='0.5s'/>Bitte frag mich nach dem heutigen Essen.</speak>"

        alexa_response = {
            "version": "1.0",
            "sessionAttributes": {},  # <-- hinzugefügt!
            "response": {
                "outputSpeech": {
                    "type": "SSML",
                    "ssml": speech_text
                },
                "shouldEndSession": True
            }
        }
        return jsonify(alexa_response)

    elif alexa_request['request']['type'] == 'SessionEndedRequest':
        # Wichtig: SessionEndedRequest sauber mit 200 OK beantworten
        return ('', 200)

    else:
        # Wenn Request-Typ unbekannt ist
        speech_text = "<speak>Entschuldigung, ich verstehe nur Anfragen zur Mensa.</speak>"
        alexa_response = {
            "version": "1.0",
            "sessionAttributes": {},  # <-- hinzugefügt!
            "response": {
                "outputSpeech": {
                    "type": "SSML",
                    "ssml": speech_text
                },
                "shouldEndSession": True
            }
        }
        return jsonify(alexa_response)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
