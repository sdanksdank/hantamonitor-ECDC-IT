import streamlit as st
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import re
import pandas as pd
from datetime import datetime

# --- CONFIGURAZIONE SICUREZZA ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
except:
    st.error("Configura GEMINI_API_KEY e SCRIPT_URL nei Secrets di Streamlit!")
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

# Lettura storico dal foglio Google
try:
    df = pd.read_csv(SHEET_READ_URL)
    df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d %b') # Formato data più compatto per il grafico (es. 12 Mag)
except:
    df = pd.DataFrame(columns=['Data', 'Casi Confermati', 'Casi Probabili', 'Casi Sospetti', 'Decessi'])

# Aggiornamento database
if df.empty or dati_ecdc['confermati'] != df.iloc[-1]['Casi Confermati']:
    salva_su_google(dati_ecdc)
    st.rerun()

# --- HEADER ---
st.title("Monitoraggio Andes Hantavirus")
st.markdown(f"**Sorgente ECDC:** [Link Ufficiale]({URL_ECDC})")

# Barra del Rischio EU
colori = {"Molto Basso": "#28a745", "Basso": "#007bff", "Moderato": "#ffc107", "Alto": "#dc3545", "Molto Alto": "#8b0000"}
colore = colori.get(livello_rischio, "#6c757d")
st.markdown(f"""<div style="background-color:#f0f2f6;padding:1rem;border-radius:10px;border-left:8px solid {colore};margin-bottom:25px;">
    <h3 style="margin:0;color:{colore};">RISCHIO EU/EEA: {livello_rischio.upper()}</h3></div>""", unsafe_allow_html=True)

# --- GRAFICO IN RIQUADRO (PULITO) ---
st.subheader("Andamento Temporale dei Casi")
if not df.empty:
    with st.container():
        st.markdown('<div style="border: 1px solid #ddd; border-radius: 10px; padding: 10px; background-color: #ffffff;">', unsafe_allow_html=True)
        fig = go.Figure()
        # Linea Confermati
        fig.add_trace(go.Scatter(x=df['Data'], y=df['Casi Confermati'], name="Casi Confermati", 
                                 line=dict(color='#dc3545', width=4), mode='lines+markers'))
        # Linea Decessi
        fig.add_trace(go.Scatter(x=df['Data'], y=df['Decessi'], name="Decessi", 
                                 line=dict(color='#000000', width=2), mode='lines+markers'))
        
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_white", 
            margin=dict(l=20,r=20,b=20,t=40),
            xaxis=dict(type='category', title="Data Rilevazione"),
            yaxis=dict(title="Numero Casi", gridcolor='#f0f0f0'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- METRICHE IN RIQUADRI ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Riepilogo Dati Attuali")
m1, m2, m3, m4 = st.columns(4)

def box_metrica(titolo, specifica, valore, colore_bordo):
    return f"""
    <div style="border: 2px solid {colore_bordo}; border-radius: 10px; padding: 15px; text-align: center; background-color: white;">
        <h4 style="margin: 0; color: #555; font-size: 0.9rem;">{titolo}</h4>
        <p style="margin: 0; color: #888; font-size: 0.7rem; text-transform: uppercase;">{specifica}</p>
        <h2 style="margin: 10px 0 0 0; color: {colore_bordo}; font-size: 2.2rem;">{valore}</h2>
    </div>
    """

m1.markdown(box_metrica("CASI CONFERMATI", "MONDO", dati_ecdc['confermati'], "#dc3545"), unsafe_allow_html=True)
m2.markdown(box_metrica("DECESSI", "MONDO", dati_ecdc['morti'], "#000000"), unsafe_allow_html=True)
m3.markdown(box_metrica("CASI PROBABILI", "MONDO", dati_ecdc['probabili'], "#fd7e14"), unsafe_allow_html=True)
m4.markdown(box_metrica("MONITORAGGIO", "ITALIA", dati_ecdc['italia_quarantena'], "#007bff"), unsafe_allow_html=True)

# --- LEGENDA FISSA ---
st.markdown("<br><hr>", unsafe_allow_html=True)
st.subheader("Legenda Definizioni")
col_l1, col_l2, col_l3 = st.columns(3)

with col_l1:
    st.markdown("""<div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff; min-height: 120px;">
    <strong>Caso Sospetto:</strong> Persona esposta (es. nave MV Hondius) con febbre e sintomi gastrointestinali o respiratori.
    </div>""", unsafe_allow_html=True)

with col_l2:
    st.markdown("""<div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #fd7e14; min-height: 120px;">
    <strong>Caso Probabile:</strong> Persona con sintomi clinici e un legame epidemiologico confermato con un altro caso.
    </div>""", unsafe_allow_html=True)

with col_l3:
    st.markdown("""<div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #dc3545; min-height: 120px;">
    <strong>Caso Confermato:</strong> Caso che soddisfa i criteri clinici ed è confermato da test di laboratorio (PCR o sierologia).
    </div>""", unsafe_allow_html=True)

# Auto-refresh ogni ora
st.components.v1.html(f"<script>setTimeout(function(){{window.location.reload();}}, 3600000);</script>", height=0)
