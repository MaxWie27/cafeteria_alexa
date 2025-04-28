from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from webscraper import get_mensa_today_filtered
import json

app = Flask(__name__)

@app.route('/mensa', methods=['GET'])
def mensa_heute():
    url = "https://www.studierendenwerk-aachen.de/speiseplaene/eupenerstrasse-w.html"
    essen = get_mensa_today_filtered(url)

    if not essen["gerichte"]:
        antwort = "Heute gibt es keine Angaben zur Mensa."
    else:
        antwort = "Heute gibt es: "
        antwort += ", ".join(essen["gerichte"])
        if essen["beilagen"]:
            antwort += ". Als Beilage: " + ", ".join(essen["beilagen"])

    # Manuelles JSON erzeugen, UTF-8 korrekt
    response_data = {"response": antwort}
    return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json')

# Hier noch deine Funktion `get_mensa_today_and_tomorrow_filtered()` reinkopieren

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
