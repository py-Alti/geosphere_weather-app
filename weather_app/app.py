#Diese Datei ist für den Aufbau des User Interfaces in einem Webbrowser. Dafür wird Streamlit verwendet.
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
from datetime import date
from weather_app.config import Config
from weather_app import db
from weather_app.pipeline import run_pipeline
from weather_app.services import (
    check_internet,
    date_to_iso_start,
    safe_filename,
    export_pdf_plot_multi,
    export_dataframe_as_xlsx,
    station_picker,
)



#Abruf der Parameter aus config.py
cfg = Config()
ALL_PARAMETERS = list(cfg.PARAMETER_LABELS.keys())


#Überschriften/Titel/Angabe der Datenquelle - Streamlit Seite
st.set_page_config(page_title="Datenbank - Geosphere-Austria-Wetterdaten für Zeitreihenanalysen", layout="wide")
st.title("Geosphere-Austria-Wetterdaten - Zeitreihenanalyse")
st.caption("Datenquelle: SQLite - Tabelle `messwerte`")


#Sidebar-Button für das Überprüfen des Online-Status während die Streamlit-App ausgeführt wird (max. Timeout = 2 Sekunden). Statusmeldung wird angezeigt
if "is_online" not in st.session_state:
    st.session_state.is_online = True

st.sidebar.markdown("---")
if st.sidebar.button("🔄️ Online-Status überprüfen"):
    st.session_state.is_online = check_internet(timeout=2.0)
    st.rerun()

if st.session_state.is_online:
    st.markdown("✅ - Internetverbindung besteht - Es können neue Wetterdaten abgerufen bzw. neue Messstationen hinzugefügt werden")
else:
    st.markdown("❌ - Internetverbindung unterbrochen - Es kann nur mit bestehenden Daten gearbeitet werden. Neue Daten/Messstationen können NICHT hinzugefügt/abgerufen werden")
st.markdown("---")


#Verfügbare Messstationen und Messstationen für die schon Werte abgerufen wurden, werden aus der DB-Tabelle wetterstationen in der SQLite-DB weather_datas_db abgefragt. Dabei werden die Rückgabewerte gecached und die Verbindung zur Datenbank abschließend wieder beendet.

@st.cache_data
def load_stations_all():
    conn = db.connect(cfg.DB_FILE)
    try:
        return db.load_stations(conn, cfg.TABLE_STATIONS)
    finally:
        conn.close()

@st.cache_data
def load_stations_with_data():
    conn = db.connect(cfg.DB_FILE)
    try:
        return db.stations_with_data(conn, cfg.TABLE_MESSWERTE)
    finally:
        conn.close()

stations_df = load_stations_all()
stations_in_db = load_stations_with_data()

station_id_to_display = dict(
    zip(stations_df["station_id"], stations_df["station_name"] + " (" + stations_df["state"] + ")")
)

stations_df_ui = stations_df[stations_df["station_id"].isin(stations_in_db)].copy()


#Sidebar-Header
st.sidebar.header("Einstellungen/Auswahl für Diagramm")


#Sidebar - Auswahl der Stationen, für die schon Messwerte vorliegen -> Fehlerbehandlung falls keine Daten vorliegen
if stations_df_ui.empty:
    st.sidebar.warning("Es liegen noch keine Messdaten vor.\nBitte zuerst eine Station importieren.")
    st.stop()

selected_station_id = station_picker(
    st.sidebar,
    stations_df_ui,
    "sidebar",
    "Messstation auswählen"
)

#Sidebar - Button für manuelle Aktualisierung der Messdaten der ausgewählten Station 
st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Datenaktualisierung")

if st.sidebar.button("Messwerte ausgewählte Station aktualisieren"):
    with st.spinner("Aktualisiere Messwerte für die ausgewählte Station..."):
        st.session_state.is_online = check_internet(timeout=2.0)

        if not st.session_state.is_online:
            st.sidebar.info("Aktualisierung nicht möglich – keine Internetverbindung.")
        else:
            try:
                run_pipeline(cfg, station_id=int(selected_station_id))
                st.sidebar.success("✅ Messwerte aktualisiert")
                st.cache_data.clear()   # wichtig: df + last_import + stations_with_data neu laden
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ Aktualisierung fehlgeschlagen:\n\n{e}")
                

#Auto-Update beim Start mit Überprüfung der Internetverbindung und Fehlermeldungen, falls diese fehlschlägt
run_key = f"pipeline_run_{selected_station_id}"
if run_key not in st.session_state:
    with st.spinner("Überprüfe auf neue Daten..."):
        st.session_state.is_online = check_internet(timeout=2.0)

        if st.session_state.is_online:
            try:
                run_pipeline(cfg, station_id=int(selected_station_id))
            except Exception as e:
                st.error(f"❗Datenimport fehlgeschlagen. Fehler:\n\n{e}")
        else:
            st.info("Internetverbindung fehlgeschlagen.\n\nEs kann mit den vorhandenen Daten weitergearbeitet werden.")
    st.session_state[run_key] = True
    st.cache_data.clear()


#Start Ladevorgang der Messwerte
@st.cache_data
def load_data(station_id):
    conn = db.connect(cfg.DB_FILE)
    try:
        return db.load_measurements(conn, cfg.TABLE_MESSWERTE, station_id)
    finally:
        conn.close()

df = load_data(int(selected_station_id))


#Import Feature für neue Messstationen, die in der DB erfasst werden sollen
st.markdown("⬇️Neue Messstationen importieren:")
st.caption("Wichtiger Hinweis: Es werden alle Messstationen, unabhängig von ihrem Status (bereits importiert ja/nein) angezeigt.")

with st.container():
    c1, c2, c3 = st.columns([2, 2, 2])

    with c1:
        import_station_id = station_picker(
            c1,
            stations_df,
            "import",
            "Stationsauswahl für Import"
        )
    with c2:
        start_date = c2.date_input("Default-Startdatum-Import", value=date(2026, 3, 1))
        start_iso = date_to_iso_start(start_date)
    with c3:
        if c3.button("Ausführen Importvorgang"):
            with st.spinner("Abfrage/Import-Messdaten läuft..."):
                st.session_state.is_online = check_internet(timeout=2.0)
                if not st.session_state.is_online:
                    st.info("Import aktuell nicht möglich.\nDie Internetverbindung ist unterbrochen")
                else:
                    try:
                        run_pipeline(cfg, station_id=int(import_station_id), start_date=start_iso)
                        st.success("✅ Import abgeschlossen")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Fehler beim Erstimport:\n\n{e}")

st.markdown("---")


#Sidebar - Auswahl der Parameter -> Mehrfachauswahl möglich
st.sidebar.subheader("Auswahl Parameter für Diagramm \n(Mehrfachauswahl möglich)")

selected_parameters = []
for p in ALL_PARAMETERS:
    if st.sidebar.checkbox(cfg.PARAMETER_LABELS[p], value=(p == "Temperatur")):
        selected_parameters.append(p)


#Sidebar - Auswahl angezeigter Diagramm Zeitraum
st.sidebar.markdown("---")
st.sidebar.subheader("Zeitraum festlegen")

start_date = df["timestamp"].min().date()
end_date = df["timestamp"].max().date()

date_range = st.sidebar.date_input(
    "Auwahl Datumsbereich",
    value=(start_date, end_date),
    min_value=start_date,
    max_value=end_date
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = start_date, end_date

display_range = (df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)
df_plot = df.loc[display_range].copy()


#Liniendiagramm der Messwert-Parameter für den ausgewählten Zeitraum
station_display = station_id_to_display.get(int(selected_station_id), str(selected_station_id))
line_chart = station_display

if not selected_parameters:
    st.info("Zumindest ein Parameter muss ausgewählt sein")
else:
    if df_plot.empty:
        st.warning("Im ausgewählten Zeitraum sind keine Daten vorhanden")
    else:
        st.subheader(f"{line_chart} - Zeitreihe")
        st.line_chart(df_plot.set_index("timestamp")[selected_parameters])


#Sidebar - PDF/Excel-Export (falls Excel-Export fehlschlägt, wird als CSV exportiert)
pdf_buffer = None
export_bytes = None
export_ext = None

if selected_parameters and not df_plot.empty:
    pdf_buffer = export_pdf_plot_multi(
        df_plot,
        selected_parameters,
        f"{station_display} - Zeitraum Messungen ({start_date} - {end_date})",
        cfg.PARAMETER_LABELS
    )

    export_df = df_plot[["timestamp"] + selected_parameters].copy()
    export_df = export_df.rename(columns={"timestamp": "Zeitstempel"})
    export_bytes, export_ext = export_dataframe_as_xlsx(export_df)

st.sidebar.markdown("---")
st.sidebar.subheader("Exporte PDF/XLSX")

if pdf_buffer is not None and export_bytes is not None:
    safe_station = safe_filename(station_display)

    st.sidebar.download_button(
        "📄 Zeitreihe als PDF",
        data=pdf_buffer,
        file_name=f"{safe_station}_{start_date}_{end_date}.pdf",
        mime="application/pdf"
    )

    if export_ext == "xlsx":
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"messwerte_{safe_station}_{start_date}_{end_date}.xlsx"
        label = "📊 Messwerte als XLSX"
    else:
        mime = "text/csv"
        filename = f"messwerte_{safe_station}_{start_date}_{end_date}.csv"
        label = "📊 Messwerte als CSV (Fallback)"

    st.sidebar.download_button(
        label,
        data=export_bytes,
        file_name=filename,
        mime=mime
    )
else:
    st.sidebar.info("Export ist aktiv, sobald Parameter gewählt sind und Daten im Zeitraum vorliegen.")


#Statistik und Messwerttabelle für ausgewählte Daten
if selected_parameters and not df_plot.empty:
    with st.expander("Statistik"):
        stats = (
            df_plot[selected_parameters]
            .agg(["count", "min", "max", "mean", "median"])
            .rename(index={
                "count": "Anzahl der Messwerte",
                "min": "Minimaler Messwert",
                "max": "Maximaler Messwert",
                "mean": "Durchschnittlicher Messwert",
                "median": "Mittlerer Messwert",
            })
            .T.round(1)
        )
        st.dataframe(stats, use_container_width=True)

    with st.expander("🗄️ Tabellenansicht"):
        table_df = df_plot[["timestamp"] + selected_parameters].rename(columns={"timestamp": "Zeitstempel"})
        st.dataframe(table_df, use_container_width=True)
        

#Sidebar - Anzeige letzter Import
@st.cache_data
def last_import(station_id):
    conn = db.connect(cfg.DB_FILE)
    try:
        return db.get_last_timestamp(conn, cfg.TABLE_MESSWERTE, station_id)
    finally:
        conn.close()
 
st.sidebar.markdown("---")
st.sidebar.subheader("Letzte Aktualisierung")

last_ts = last_import(int(selected_station_id))

if last_ts:
    from datetime import datetime
    dt = datetime.fromisoformat(last_ts)
    st.sidebar.info(f"Letzte Aktualisierung:\n\n{dt.strftime('%d.%m.%Y %H:%M')}")
else:
    st.sidebar.info("Für diese Station sind noch keine Daten vorhanden") 