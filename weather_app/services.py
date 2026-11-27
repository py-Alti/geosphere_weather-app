# In diesem Skript werden Funtkionen verwaltet, welche den Online-Status überprüft bzw. den Export als PDF und XLSX ermöglicht und die Filterfunktion der Messstationen ermöglicht

import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date


# Check ob eine Internet Verbindung besteht oder nicht (maximaler Timeout = 2 Sekunden)

def check_internet(timeout=2.0):
    test_url = [
        "https://dataset.api.hub.geosphere.at/v1/datasets"
    ]
    for url in test_url:
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
    return False



# Umwandlung der Zeitangaben in ein ISO-Format

def date_to_iso_start(d):
    return f"{d.isoformat()}T00:00"


# Funktion für das Erstellen von Dateinamen, bei denen Umlaute und Sonderzeichen entsprechend (ersetzt durch _) umgewandelt werden

def safe_filename(name):
    return "".join(c if c.isalnum() or c in " _-()" else "_" for c in name).replace(" ", "_")


# Exportfunktion die Ausgabe des Zeitreihen-Diagramms als PDF

def export_pdf_plot_multi(df, columns, title, parameter_labels):
    fig, ax = plt.subplots(figsize=(10, 5))
    
    for col in columns:
        label = parameter_labels.get(col, col)
        ax.plot(df["timestamp"], df[col], linewidth=1.5, label=label)
    
    ax.set_title(title)
    ax.set_xlabel("Zeit")
    ax.grid(True)
    ax.legend()
    
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    buf.seek(0)
    return buf


# Exportfunktion des Dataframes als XLSX, mit der Möglichkeit des Exports als CSV, falls der XLSX-Export fehlschlägt 

def export_dataframe_as_xlsx(df):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Messwerte")
        return output.getvalue(), "xlsx"
    except Exception:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return csv_bytes, "csv"
 

#     Filterfunktion zur Auswahl der Messtation -> Filter über Bundesland

def station_picker(container, df, prefix, title):
    state = container.selectbox(
        "Bundesland",
        ["Alle"] + sorted(df["state"].unique()),
        key=f"{prefix}_state"
    )

    search = container.text_input(
        "🔎 Station suchen",
        key=f"{prefix}_search"
    )

    filtered = df.copy()

    if state != "Alle":
        filtered = filtered[filtered["state"] == state]

    if search:
        s = search.casefold()
        filtered = filtered[
            filtered["station_name"].str.casefold().str.contains(s) |
            filtered["state"].str.casefold().str.contains(s) |
            filtered["station_id"].astype(str).str.contains(s)
        ]

    if filtered.empty:
        container.warning("Keine Treffer – bitte Suche/Bundesland anpassen.")
        filtered = df.copy()

    label_to_id = dict(zip(filtered["__label"], filtered["station_id"]))
    label = container.selectbox(title, list(label_to_id.keys()), key=f"{prefix}_select")
    return int(label_to_id[label])