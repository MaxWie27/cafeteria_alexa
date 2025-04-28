from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import html
import os

app = Flask(__name__)

def clean_text(text):
    # Erst alles nach <sup> abschneiden
    text = text.split('<sup')[0]

    # Aus <span class="seperator">oder</span> echtes " oder " machen
    text = text.replace('<span class="seperator">oder</span>', ' oder ')

    # Danach normalen HTML-Text extrahieren
    text = BeautifulSoup(text, 'html.parser').get_text()

    # Pluszeichen entfernen
    text = text.replace('+', '').strip()

    # HTML Entities auflösen (z.B. &uuml; → ü)
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

@app.route('/mensa', methods=['GET'])
def mensa():
    url = "https://www.studierendenwerk-aachen.de/speiseplaene/eupenerstrasse-w.html"
    essen = get_mensa_today_filtered(url)

    if not essen["gerichte"]:
        speech_text = "Heute gibt es keine Angaben zur Mensa."
    else:
        speech_text = "Heute gibt es: "
        speech_text += ", ".join(essen["gerichte"])
        if essen["beilagen"]:
            speech_text += ". Als Beilage: " + ", ".join(essen["beilagen"])

    alexa_response = {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech_text
            },
            "shouldEndSession": True
        }
    }

    return jsonify(alexa_response)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
