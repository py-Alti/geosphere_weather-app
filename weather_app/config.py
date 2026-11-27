import os

#Hier wird die Konfiguration der Datenbank, API und Mapping der Parameter zwischen RAW-Messwerte und transformierte Messwerte verwaltet bzw. die Labels für das Userinterface definiert.

class Config:
    def __init__(self):
        
        # Datenbank
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        self.DB_FILE = os.path.join(BASE_DIR, "weather_datas_db.db")
        self.TABLE_MESSWERTE = "messwerte"
        self.TABLE_RAW = "messwerte_raw"
        self.TABLE_STATIONS = "wetterstationen"
        self.VIEW_NAME = "vw_messwerte"
    
    
        # Geosphere Austria-API
        self.BASE_URL = "https://dataset.api.hub.geosphere.at/v1"
        self.RESOURCE = "klima-v2-1h"
        self.PARAMETERS = ["rf", "tl", "rr", "ff", "p"]
        
        
        # Default-Einstellungen Messwerte Import
        self.DEFAULT_START = "2026-03-01T00:00"
        self.OVERLAP_HOURS = 2
        
        
        # Mapping der Messwerte Parameter zwischen Tabelle messwerte_raw (Ursprungstabelle) und messwerte (Zieltabelle) in der Datenbank
        self.PARAM_MAP = {
            "RF": "Luftfeuchtigkeit",
            "TL": "Temperatur",
            "RR": "Niederschlag",
            "FF": "Windgeschwindigkeit",
            "P":  "Luftdruck"
        }
        
        self.TARGET_COLUMNS = [
            "Luftfeuchtigkeit",
            "Temperatur",
            "Niederschlag",
            "Windgeschwindigkeit",
            "Luftdruck"
        ]
        
        # Labels für UI
        self.PARAMETER_LABELS = {
            "Luftfeuchtigkeit": "Luftfeuchtigkeit (%)",
            "Temperatur": "Temperatur (°C)",
            "Niederschlag": "Niederschlag (mm)",
            "Windgeschwindigkeit": "Windgeschwindigkeit (m/s)",
            "Luftdruck": "Luftdruck (hPa)",
        }