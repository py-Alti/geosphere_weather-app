# Geosphere Weather App

Abschlussprojekt - für meinen WIFI Python-Diplomkurs 
Diese Streamlit soll dazu dienen, Daten vom Geosphere Austria Datahub abzurufen. Die Messwerte werden lokal, in einer SQLite-DB abgespeichert. Die Features dieses Projekts, können mittels Streamlit, im Webbrowser benutzt werden.

## Features

- Auswahl von Messstationen
- Automatischer & manueller Datenimport
- Zeitreihenanalyse mehrerer Parameter
- Filter nach Zeitraum
- Export:
  - PDF (Diagramm)
  - Excel / CSV (Messwerte)
- Statistische Auswertungen

## Tech Stack
- Python 3.13.5
- SQLite

## Architektur

Das Projekt besteht aus folgenden Komponenten:

- `app.py` → Streamlit UI
- `pipeline.py` → Datenimport & Verarbeitung
- `db.py` → SQLite-Datenbankzugriff
- `services.py` → Hilfsfunktionen
- `config.py` → zentrale Konfiguration

## Requirements
pip install -r requirements.txt
