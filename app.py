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
SHEET_READ_URL = "https://docs.google.com/spreadsheets/d/1eWV8lUp3QM8_t2LDK6rjXTSRrWYxOXehFrgIv-CCNKs/export?format=csv"

def traduci_rischio(rischio_en):
    traduzioni = {
        "very low": "Molto Basso",
        "low": "Basso",
        "moderate": "Moderato",
        "high": "Alto",
        "very high": "Molto Alto"
    }
    return traduzioni.get(rischio_en.lower(), rischio_en)

def fetch_ecdc_data():
    try:
        res = requests.get(URL_ECDC, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        testo = soup.get_text()[:5000]
        
        rischio_en = "Very Low"
        risk_match = re.search(r'risk to the EU/EEA general population is\s+([\w\s]+)\.', testo, re.IGNORECASE)
        if risk_match: rischio_en = risk_match.group(1).strip()

        prompt = "Analizza report ECDC. Estrai numeri Andes Hantavirus. Restituisci SOLO JSON: {'confermati': int, 'morti': int, 'probabili': int, 'sospetti': int, 'italia_quarantena': int}"
        payload = {"contents": [{"parts": [{"text": prompt + " Testo: " + testo}]}]}
        api_res = requests.post(URL_API, json=payload)
        dati_ia = json.loads(re.search(r'\{.*\}', api_res.json()['candidates'][0]['content']['parts'][0]['text'], re.DOTALL).group())
        return dati_ia, traduci_rischio(rischio_en)
    except:
        return {"confermati": 9, "morti": 3, "probabili": 2, "sospetti": 0, "italia_quarantena": 4}, "Molto Basso"

def salva_su_google(dati):
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
        pass

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Monitoraggio Andes", layout="wide")

dati_ecdc, livello_rischio = fetch_ecdc_data()

# Lettura storico
try:
    df = pd.read_csv(SHEET_READ_URL)
    # Pulizia date: converte in datetime e rimuove millisecondi
    df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%Y-%m-%d %H:00')
except:
    df = pd.DataFrame(columns=['Data', 'Casi Confermati', 'Casi Probabili', 'Casi Sospetti', 'Decessi'])

# Aggiornamento database
if df.empty or dati_ecdc['confermati'] != df.iloc[-1]['Casi Confermati']:
    salva_su_google(dati_ecdc)
    st.rerun()

# --- HEADER ---
st.title("Monitoraggio Andes Hantavirus")
st.markdown(f"**Sorgente ECDC:** [Link Ufficiale]({URL_ECDC})")

# Barra del Rischio
colori = {"Molto Basso": "#28a745", "Basso": "#007bff", "Moderato": "#ffc107", "Alto": "#dc3545", "Molto Alto": "#8b0000"}
colore = colori.get(livello_rischio, "#6c757d")
st.markdown(f"""<div style="background-color:#f0f2f6;padding:1rem;border-radius:10px;border-left:8px solid {colore};margin-bottom:25px;">
    <h3 style="margin:0;color:{colore};">RISCHIO EU/EEA: {livello_rischio.upper()}</h3></div>""", unsafe_allow_html=True)

# --- GRAFICO (SOPRA) ---
st.subheader("Andamento Temporale dei Casi")
if not df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Data'], y=df['Casi Confermati'], name="Confermati", line=dict(color='red', width=3), mode='lines+markers'))
    fig.add_trace(go.Scatter(x=df['Data'], y=df['Decessi'], name="Decessi", line=dict(color='black', width=2), mode='lines+markers'))
    fig.update_layout(
        hovermode="x unified", 
        template="plotly_white", 
        margin=dict(l=0,r=0,b=0,t=40),
        xaxis=dict(type='category') # Forza la visualizzazione come categorie per evitare scale temporali strane
    )
    st.plotly_chart(fig, use_container_width=True)

# --- METRICHE IN RIQUADRI (SOTTO IL GRAFICO) ---
st.markdown("### Riepilogo Dati Attuali")
m1, m2, m3, m4 = st.columns(4)

def box_metrica(titolo, valore, colore_bordo):
    return f"""
    <div style="border: 2px solid {colore_bordo}; border-radius: 10px; padding: 15px; text-align: center; background-color: white;">
        <h4 style="margin: 0; color: #555; font-size: 0.9rem;">{titolo}</h4>
        <h2 style="margin: 10px 0 0 0; color: {colore_bordo}; font-size: 2.2rem;">{valore}</h2>
    </div>
    """

m1.markdown(box_metrica("CASI CONFERMATI", dati_ecdc['confermati'], "#dc3545"), unsafe_allow_html=True)
m2.markdown(box_metrica("DECESSI", dati_ecdc['morti'], "#000000"), unsafe_allow_html=True)
m3.markdown(box_metrica("CASI PROBABILI", dati_ecdc['probabili'], "#fd7e14"), unsafe_allow_html=True)
m4.markdown(box_metrica("SOSPETTI / IT", dati_ecdc['italia_quarantena'], "#007bff"), unsafe_allow_html=True)

# --- LEGENDA FISSA IN RIQUADRI ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Legenda Definizioni")
col_l1, col_l2 = st.columns(2)

with col_l1:
    st.markdown("""<div style="background-color: #e7f3fe; padding: 15px; border-radius: 10px; border-left: 5px solid #2196F3; height: 100px;">
    <strong>Caso Sospetto:</strong> Persona esposta (es. nave MV Hondius) con febbre e sintomi gastrointestinali o respiratori.
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""<div style="background-color: #e7f3fe; padding: 15px; border-radius: 10px; border-left: 5px solid #2196F3; height: 100px;">
    <strong>Caso Probabile:</strong> Persona con sintomi clinici e un legame epidemiologico confermato con un altro caso.
    </div>""", unsafe_allow_html=True)

with col_l2:
    st.markdown("""<div style="background-color: #e7f3fe; padding: 15px; border-radius: 10px; border-left: 5px solid #2196F3; height: 100px;">
    <strong>Caso Confermato:</strong> Caso che soddisfa i criteri clinici ed è confermato da test di laboratorio (PCR o sierologia).
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""<div style="background-color: #e7f3fe; padding: 15px; border-radius: 10px; border-left: 5px solid #2196F3; height: 100px;">
    <strong>Rischio EU/EEA:</strong> Livello di minaccia valutato per i cittadini europei in base alla trasmissibilità attuale.
    </div>""", unsafe_allow_html=True)

# Auto-refresh ogni ora
st.components.v1.html(f"<script>setTimeout(function(){{window.location.reload();}}, 3600000);</script>", height=0)
