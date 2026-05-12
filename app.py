import streamlit as st
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import re
import pandas as pd
from datetime import datetime

# --- CONFIGURAZIONE ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
except:
    st.error("Configura GEMINI_API_KEY e SCRIPT_URL nei Secrets!")
    st.stop()

URL_API = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
URL_ECDC = "https://www.ecdc.europa.eu/en/infectious-disease-topics/hantavirus-infection/surveillance-and-updates/andes-hantavirus-outbreak"
# URL per la lettura pubblica del tuo foglio in formato CSV
SHEET_READ_URL = "https://docs.google.com/spreadsheets/d/1eWV8lUp3QM8_t2LDK6rjXTSRrWYxOXehFrgIv-CCNKs/export?format=csv"

def fetch_ecdc_data():
    try:
        res = requests.get(URL_ECDC, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        testo = soup.get_text()[:5000]
        
        # Estrazione Valutazione Rischio
        rischio = "Very Low"
        risk_match = re.search(r'risk to the EU/EEA general population is\s+([\w\s]+)\.', testo, re.IGNORECASE)
        if risk_match: rischio = risk_match.group(1).strip()

        prompt = "Analizza report ECDC. Estrai numeri Andes Hantavirus. Restituisci SOLO JSON: {'confermati': int, 'morti': int, 'probabili': int, 'sospetti': int, 'italia_quarantena': int}"
        payload = {"contents": [{"parts": [{"text": prompt + " Testo: " + testo}]}]}
        api_res = requests.post(URL_API, json=payload)
        dati_ia = json.loads(re.search(r'\{.*\}', api_res.json()['candidates'][0]['content']['parts'][0]['text'], re.DOTALL).group())
        return dati_ia, rischio
    except:
        return {"confermati": 9, "morti": 3, "probabili": 2, "sospetti": 0, "italia_quarantena": 4}, "Very Low"

def salva_su_google(dati):
    # Invia i dati al ponte Google Apps Script (Metodo GET)
    params = {
        "data": datetime.now().strftime("%Y-%m-%d %H:00"),
        "confermati": dati['confermati'],
        "probabili": dati['probabili'],
        "sospetti": dati['sospetti'] + dati['italia_quarantena'],
        "decessi": dati['morti']
    }
    try:
        requests.get(SCRIPT_URL, params=params, timeout=10)
    except:
        st.error("Errore di connessione al ponte Google.")

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Andes Virus Monitor", layout="wide")

# 1. Recupero dati attuali dall'ECDC
dati_ecdc, livello_rischio = fetch_ecdc_data()

# 2. Lettura dello storico dal foglio Google
try:
    df = pd.read_csv(SHEET_READ_URL)
except:
    df = pd.DataFrame(columns=['Data', 'Casi Confermati', 'Casi Probabili', 'Casi Sospetti', 'Decessi'])

# 3. Logica di aggiornamento: se il foglio è vuoto o i dati sono nuovi, salva!
if df.empty:
    salva_su_google(dati_ecdc)
    st.rerun()
else:
    ultimo_confermato = df.iloc[-1]['Casi Confermati']
    ultimo_decesso = df.iloc[-1]['Decessi']
    if dati_ecdc['confermati'] != ultimo_confermato or dati_ecdc['morti'] != ultimo_decesso:
        salva_su_google(dati_ecdc)
        st.rerun()

# --- RENDERING UI ---
st.title("🛡️ Monitoraggio Mondiale ECDC - Andes Hantavirus")
st.caption(f"Sorgente: {URL_ECDC}")

# Barra del Rischio
colori = {"very low": "#28a745", "low": "#007bff", "moderate": "#ffc107", "high": "#dc3545"}
colore = colori.get(livello_rischio.lower(), "#6c757d")
st.markdown(f"""<div style="background-color:#f0f2f6;padding:1rem;border-radius:10px;border-left:8px solid {colore};">
    <h3 style="margin:0;color:{colore};">RISCHIO EU/EEA: {livello_rischio.upper()}</h3></div>""", unsafe_allow_html=True)

# Metriche
m1, m2, m3, m4 = st.columns(4)
m1.metric("CONFERMATI", dati_ecdc['confermati'])
m2.metric("DECESSI", dati_ecdc['morti'])
m3.metric("PROBABILI", dati_ecdc['probabili'])
m4.metric("SOSPETTI/IT", dati_ecdc['italia_quarantena'])

# Grafico
st.subheader("📈 Curva Epidemiologica (Database Google)")
if not df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Data'], y=df['Casi Confermati'], name="Confermati", line=dict(color='red', width=3), mode='lines+markers'))
    fig.add_trace(go.Scatter(x=df['Data'], y=df['Decessi'], name="Decessi", line=dict(color='black', width=2), mode='lines+markers'))
    fig.update_layout(hovermode="x unified", template="plotly_white", margin=dict(l=0,r=0,b=0,t=40))
    st.plotly_chart(fig, use_container_width=True)

# Auto-refresh ogni ora
st.components.v1.html(f"<script>setTimeout(function(){{window.location.reload();}}, 3600000);</script>", height=0)
