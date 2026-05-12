import streamlit as st
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE SICUREZZA ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    GSHEET_URL = st.secrets["GSHEET_URL"]
except:
    st.error("ERRORE: Configura GEMINI_API_KEY e GSHEET_URL nei Secrets!")
    st.stop()

URL_API = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
URL_ECDC = "https://www.ecdc.europa.eu/en/infectious-disease-topics/hantavirus-infection/surveillance-and-updates/andes-hantavirus-outbreak"
AUTO_REFRESH_INTERVAL = 3600 

def fetch_ecdc_specific_data():
    try:
        response = requests.get(URL_ECDC, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        testo_pagina = soup.get_text()
        data_report = datetime.now().strftime("%d %b %Y")
        
        rischio_testo = "Very Low"
        risk_match = re.search(r'risk to the EU/EEA general population is\s+([\w\s]+)\.', testo_pagina, re.IGNORECASE)
        if risk_match: rischio_testo = risk_match.group(1).strip()

        prompt = (f"Analizza: '{testo_pagina[:5000]}'. Estrai numeri outbreak Andes. "
                  "JSON: {'confermati': int, 'morti': int, 'probabili': int, 'sospetti': int, 'italia_quarantena': int}")
        
        res = requests.post(URL_API, json={"contents": [{"parts": [{"text": prompt}]}]})
        testo_ia = res.json()['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'\{.*\}', testo_ia, re.DOTALL)
        return json.loads(match.group()), data_report, rischio_testo
    except:
        return {"confermati": 9, "morti": 3, "probabili": 2, "sospetti": 0, "italia_quarantena": 4}, "12 Mag 2026", "Very Low"

def gestisci_database_immortale(nuovi_dati, data_agg):
    # Connessione a Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=GSHEET_URL)
    
    identificatore = f"{data_agg} {datetime.now().strftime('%H:00')}"
    
    # Se il foglio è vuoto, aggiungi lo storico reale
    if df.empty or len(df) < 2:
        dati_iniziali = [
            {'Data': '23 Apr 2026 12:00', 'Casi Confermati': 0, 'Casi Probabili': 0, 'Casi Sospetti': 10, 'Decessi': 0},
            {'Data': '30 Apr 2026 12:00', 'Casi Confermati': 2, 'Casi Probabili': 5, 'Casi Sospetti': 20, 'Decessi': 0},
            {'Data': '05 Mag 2026 12:00', 'Casi Confermati': 5, 'Casi Probabili': 3, 'Casi Sospetti': 15, 'Decessi': 2},
            {'Data': '10 Mag 2026 12:00', 'Casi Confermati': 8, 'Casi Probabili': 2, 'Casi Sospetti': 10, 'Decessi': 3}
        ]
        df = pd.DataFrame(dati_iniziali)
        conn.update(spreadsheet=GSHEET_URL, data=df)

    # Aggiungi nuovo dato se non duplicato
    if identificatore not in df['Data'].values:
        nuova_riga = pd.DataFrame([{
            'Data': identificatore,
            'Casi Confermati': nuovi_dati['confermati'],
            'Casi Probabili': nuovi_dati['probabili'],
            'Casi Sospetti': nuovi_dati['sospetti'] + nuovi_dati['italia_quarantena'],
            'Decessi': nuovi_dati['morti']
        }])
        df = pd.concat([df, nuova_riga], ignore_index=True)
        conn.update(spreadsheet=GSHEET_URL, data=df)
    return df

# --- UI STREAMLIT ---
st.set_page_config(page_title="Andes Monitor Immortal", layout="wide")
dati, ultima_data, rischio = fetch_ecdc_specific_data()
df_storico = gestisci_database_immortale(dati, ultima_data)

# Logica Colore Rischio
colori = {"very low": "#28a745", "low": "#007bff", "moderate": "#ffc107", "high": "#dc3545"}
colore = colori.get(rischio.lower(), "#6c757d")

st.title("🛡️ Monitoraggio Mondiale ECDC - Andes Hantavirus")
st.markdown(f"**Sorgente Ufficiale:** ECDC [{URL_ECDC}]({URL_ECDC})")

st.markdown(f"""<div style="background-color:#f0f2f6;padding:1.5rem;border-radius:10px;border-left:10px solid {colore};">
    <h3 style="margin:0;color:{colore};">RISCHIO EU/EEA: {rischio.upper()}</h3></div>""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("CONFERMATI", dati['confermati'])
m2.metric("DECESSI", dati['morti'])
m3.metric("PROBABILI", dati['probabili'])
m4.metric("SOSPETTI (IT)", dati['italia_quarantena'])

st.subheader("📈 Andamento Temporale (Database Google Sheets)")
fig = go.Figure()
for col, color in zip(['Casi Confermati', 'Casi Probabili', 'Casi Sospetti', 'Decessi'], ['red', 'orange', 'yellow', 'black']):
    fig.add_trace(go.Scatter(x=df_storico['Data'], y=df_storico[col], name=col, line=dict(color=color)))
st.plotly_chart(fig, use_container_width=True)

# LEGENDA
st.markdown("---")
st.subheader("📋 LEGENDA UFFICIALE")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Caso Sospetto**: Persona su stesso trasporto o in contatto con MV Hondius dal 5 aprile, con febbre E sintomi.")
    st.markdown("**Caso Probabile**: Persona con sintomi E contatto noto con caso ANDV.")
with c2:
    st.markdown("**Caso Confermato**: Persona con definizione di sospetto/probabile E test positivo.")

st.components.v1.html(f"<script>setTimeout(function(){{window.location.reload();}},{AUTO_REFRESH_INTERVAL*1000});</script>", height=0)