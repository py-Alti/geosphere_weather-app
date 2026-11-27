# Dieses Skript dient zum Abrufen von vergangenen Messwerten über die Geosphere Austria-API. Diese werden im ersten Schritt, in die messwerte_raw-Tabelle, in der SQLite-DB weather_datas_db übertragen. Im zweiten Schritt werden die Daten in die messwerte-Tabelle transformiert. Format Tabelle messwerte_raw: Es wird pro Messstation, pro Parameter, pro Zeitstempel ein Datensatz erstellt. Format Tabelle messwerte: Mit den Daten aus der Tabelle messwerte_raw werden zusammengesetzte Datensätze generiert. Stations-ID | Zeitstempel | Parameter 1 |Parameter 2 |.... Darüber hinaus wird in diesem Skript auch eine SQL-View der messwerte Tabelle erzeugt.

import requests
import pandas as pd
from datetime import datetime, timedelta
from weather_app import db


#Hier werden die Zeitstempel ohne Sekunden formatiert
def iso_no_seconds(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


#API-Client zur Kapselung des Zugriffs
class GeosphereAPI:
       
    def __init__(self, base_url, resource, parameters, timeout=(3.05, 15)):
        self.base_url = base_url
        self.resource = resource
        self.parameters = list(parameters)
        self.timeout = timeout
        

#Daten aus API abrufen    
    def fetch_from_api(self, station_id, start, end):
        url = f"{self.base_url}/station/historical/{self.resource}"
        params = {
            "station_ids": station_id,
            "parameters": ",".join(p.upper() for p in self.parameters),
            "start": start,
            "end": end,
            "format": "json"
    }
    
        r = requests.get(url, params=params, timeout=(3.05, 15))
        r.raise_for_status()
        data = r.json()                 
    
    
        timestamps = data.get("timestamps", [])
        features = data.get("features", [])

        if not features:
            return [], {}

        param_block = features[0]["properties"]["parameters"]
        return timestamps, param_block


#Klasse für den Pipeline-Ablauf
class PipelineRun:
    def __init__(self, cfg, client):
        self.cfg = cfg
        self.client = client
        
#Import der Daten aus API in die DB-Tabelle messwerte_raw
    def import_api_to_raw(self, conn, station_id, start_override=None):
        cur = conn.cursor()
        db.ensure_messwerte_raw_table(cur, self.cfg.TABLE_RAW)
        conn.commit()
    
        _, _, max_before = db.station_stats(cur, self.cfg.TABLE_RAW, station_id)

        end = iso_no_seconds(datetime.now())
        if max_before:
            start_dt = datetime.fromisoformat(max_before) - timedelta(hours=self.cfg.OVERLAP_HOURS)
            start = iso_no_seconds(start_dt)
        else:
            start = start_override or self.cfg.DEFAULT_START
    
        timestamps, param_block = self.client.fetch_from_api(station_id, start, end)

        inserted = 0
        if not timestamps or not param_block:
            return 0

        for param in self.cfg.PARAMETERS:
            key = param if param in param_block else param.upper() if param.upper() in param_block else None
            if key is None:
                continue

            values = param_block[key]["data"]
            for ts, val in zip(timestamps, values):
                if val is None:
                    continue

                cur.execute(f"""
                    INSERT OR IGNORE INTO {self.cfg.TABLE_RAW}
                    VALUES (?, ?, ?, ?)
                """, (station_id, key, ts, float(val)))

                if cur.rowcount == 1:
                    inserted += 1

        conn.commit()
        return inserted


#Umwandlung der Daten aus der DB-Tabelle messwerte_raw in die Tabelle messwerte
    def upsert_messwerte_incremental(self, conn, station_id):
        cur = conn.cursor()
        db.ensure_messwerte_table(cur, self.cfg.TABLE_MESSWERTE)
        conn.commit()

        _, _, before_max = db.station_stats(cur, self.cfg.TABLE_MESSWERTE, station_id)

        if before_max:
            start_dt = datetime.fromisoformat(before_max) - timedelta(hours=self.cfg.OVERLAP_HOURS)
            start_ts = iso_no_seconds(start_dt)
        else:
            start_ts = self.cfg.DEFAULT_START

        df_raw = pd.read_sql_query(f"""
            SELECT station_id, parameter, timestamp, value
            FROM {self.cfg.TABLE_RAW}
            WHERE station_id = ?
            AND timestamp >= ?
        """, conn, params=[station_id, start_ts])

        if df_raw.empty:
            return 0

        df_raw["parameter"] = df_raw["parameter"].str.upper()
        df_raw = df_raw[df_raw["parameter"].isin(self.cfg.PARAM_MAP.keys())].copy()
        df_raw["name"] = df_raw["parameter"].map(self.cfg.PARAM_MAP)

        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], errors="coerce")
        df_raw = df_raw.dropna(subset=["timestamp", "value"])

        wide = df_raw.pivot_table(
            index=["station_id", "timestamp"],
            columns="name",
            values="value",
            aggfunc="first"
        ).reset_index()

        if wide.empty:
            return 0

        for col in self.cfg.TARGET_COLUMNS:
            if col not in wide.columns:
                wide[col] = None

        wide["timestamp"] = wide["timestamp"].dt.strftime("%Y-%m-%dT%H:%M")

        upsert_sql = f"""
            INSERT INTO {self.cfg.TABLE_MESSWERTE} (
                station_id, timestamp,
                Windgeschwindigkeit, Luftdruck, Luftfeuchtigkeit, Niederschlag, Temperatur
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(station_id, timestamp) DO UPDATE SET
                Windgeschwindigkeit = excluded.Windgeschwindigkeit,
                Luftdruck          = excluded.Luftdruck,
                Luftfeuchtigkeit   = excluded.Luftfeuchtigkeit,
                Niederschlag       = excluded.Niederschlag,
                Temperatur         = excluded.Temperatur
        """

        rows = []
        for _, r in wide.iterrows():
            rows.append((
                int(r["station_id"]),
                r["timestamp"],
                None if pd.isna(r["Windgeschwindigkeit"]) else float(r["Windgeschwindigkeit"]),
                None if pd.isna(r["Luftdruck"]) else float(r["Luftdruck"]),
                None if pd.isna(r["Luftfeuchtigkeit"]) else float(r["Luftfeuchtigkeit"]),
                None if pd.isna(r["Niederschlag"]) else float(r["Niederschlag"]),
                None if pd.isna(r["Temperatur"]) else float(r["Temperatur"]),
            ))

        cur.executemany(upsert_sql, rows)
        conn.commit()
        return len(wide)


#Generierung einer DB-View der Tabelle messwerte
    def ensure_view(self, conn):
        cur = conn.cursor()
        db.create_or_replace_view(cur, self.cfg.VIEW_NAME, self.cfg.TABLE_MESSWERTE)
        conn.commit()
    

#Ablauf der einzelnen Funktionen, aus der Datei pipeline.py -> 1. Import API zu RAW-Tabelle -> 2. Umwandlung Messwerte aus RAW-Tabelle in Tabelle messwerte -> 3. DB-View erstellen -> 4. Datenbankverbindung schließen
    def run(self, station_id, start_date=None):
        conn = db.connect(self.cfg.DB_FILE)
        try:
            imported = self.import_api_to_raw(conn, station_id, start_override=start_date)
            updated = self.upsert_messwerte_incremental(conn, station_id)
            self.ensure_view(conn)

            return {
                "raw_imported": imported,
                "messwerte_updated": updated,
                "timestamp": datetime.now(),
                "station_id": station_id,
                "start_date_used": start_date
            }
        finally:
            conn.close()
            

def run_pipeline(cfg, station_id, start_date=None):
    client = GeosphereAPI(
        base_url=cfg.BASE_URL,
        resource=cfg.RESOURCE,
        parameters=cfg.PARAMETERS,
        timeout=(3.05, 15)
    )
    runner = PipelineRun(cfg=cfg, client=client)
    return runner.run(station_id=station_id, start_date=start_date)

