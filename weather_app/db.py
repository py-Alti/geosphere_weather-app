#In diesem Skript wird die Verbindung zur SQLite-Datenbank mit Wetterdaten hergestellt bzw. es werden die Daten auch transformiert


import sqlite3
import pandas as pd


#Verbindung zur Datenbank aufbauen
def connect(db_file):
    return sqlite3.connect(db_file)


#Aufbau der RAW-Tabelle in meiner Datenbank
def ensure_messwerte_raw_table(cur, raw_table):
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {raw_table}(
        station_id INTEGER,
        parameter TEXT,
        timestamp TEXT,
        value REAL,
        PRIMARY KEY (station_id, parameter, timestamp)
    )
    """)


#Aufbau der Messwerte-Tabelle in meiner Datenbank
def ensure_messwerte_table(cur, target_table):
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_table}(
        station_id INTEGER,
        timestamp TEXT,
        Windgeschwindigkeit REAL,
        Luftdruck REAL,
        Luftfeuchtigkeit REAL,
        Niederschlag REAL,
        Temperatur REAL,
        PRIMARY KEY (station_id, timestamp)
    )
    """)


#Erstellen einer View meiner Messwerte in meiner Datenbank
def create_or_replace_view(cur, view_name, target_table):
    cur.execute(f"DROP VIEW IF EXISTS {view_name}")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT
            station_id,
            timestamp,
            Windgeschwindigkeit,
            Luftdruck,
            Luftfeuchtigkeit,
            Niederschlag,
            Temperatur
        FROM {target_table}
    """)


#Wie viele Datensätze gibt es, in welchem Zeitraum liegen Messwerte vor
def station_stats(cur, table, station_id):
    cur.execute(f"""
        SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
        FROM {table}
        WHERE station_id = ?
    """, (station_id,))
    return cur.fetchone()


#Hier wird das Pandas-Datafram erstellt, in dem Werte umformatiert und standardisiert werden. Diese Funktion dient dazu, dass in der App, die Messstaionen in einer übersichtlichen Art dargestellt werden 
def load_stations(conn, stations_table):
    df = pd.read_sql_query(
        f"SELECT id, Stationsname, Bundesland FROM {stations_table}",
        conn
    )
    df = df.rename(columns={
        "id": "station_id",
        "Stationsname": "station_name",
        "Bundesland": "state"
    })
    df["station_id"] = df["station_id"].astype(int)
    df["__label"] = df.apply(
        lambda r: f"{r['station_id']} – {r['station_name']} ({r['state']})",
        axis=1
    )
    return df


#Welche Stationen gibt in meiner Messwerte-Tabelle. Jede Messstation wird nur einmal angezeigt
def stations_with_data(conn, messwerte_table):
    rows = conn.execute(f"SELECT DISTINCT station_id FROM {messwerte_table}").fetchall()
    return set(int(r[0]) for r in rows)


#Hier wird ein Pandas-DF erstellt, bei dem die Werte einer Messtation nach dem Zeitstempel sortiert werden
def load_measurements(conn, messwerte_table, station_id):
    df = pd.read_sql_query(
        f"SELECT * FROM {messwerte_table} WHERE station_id = ? ORDER BY timestamp",
        conn,
        params=(station_id,)
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


#Ermittlung letzter Import für Streamlit-Sidebar
def get_last_timestamp(conn, table, station_id):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MAX(timestamp)
        FROM {table}
        WHERE station_id = ?
    """, (station_id,))
    
    row = cur.fetchone()
    return row[0] if row and row[0] else None