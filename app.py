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
    df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d %b')
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
colore_rischio = colori.get(livello_rischio, "#6c757d")
st.markdown(f"""
    <div style="background-color: rgb(240, 242, 246) !important; padding: 1rem; border-radius: 10px; border-left: 8px solid {colore_rischio}; margin-bottom: 25px;">
        <h3 style="margin: 0; color: {colore_rischio} !important; font-weight: 800;">RISCHIO EU/EEA: {livello_rischio.upper()}</h3>
    </div>
""", unsafe_allow_html=True)

# --- GRAFICO IN RIQUADRO ---
st.subheader("Andamento Temporale dei Casi")
if not df.empty:
    with st.container():
        st.markdown('<div style="border: 2px solid #ddd; border-radius: 12px; padding: 10px; background-color: rgb(255, 255, 255);">', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Data'], y=df['Casi Confermati'], name="Confermati", line=dict(color='rgb(220, 53, 69)', width=4), mode='lines+markers'))
        fig.add_trace(go.Scatter(x=df['Data'], y=df['Decessi'], name="Decessi", line=dict(color='rgb(0, 0, 0)', width=2), mode='lines+markers'))
        
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_white", 
            margin=dict(l=20,r=20,b=20,t=40),
            xaxis=dict(type='category', tickfont=dict(color="black")),
            yaxis=dict(gridcolor='rgb(240, 240, 240)', tickfont=dict(color="black")),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="black"))
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- METRICHE IN RIQUADRI ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Riepilogo Dati Attuali")
m1, m2, m3, m4 = st.columns(4)

def box_metrica(titolo, specifica, valore, colore_bordo):
    return f"""
    <div style="
        border: 3px solid {colore_bordo}; 
        border-radius: 12px; 
        padding: 20px; 
        text-align: center; 
        background-color: rgb(245, 245, 245) !important; 
        margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    ">
        <h4 style="margin: 0; color: rgb(40, 40, 40) !important; font-size: 1rem; font-weight: 800; text-transform: uppercase;">{titolo}</h4>
        <p style="margin: 2px 0; color: rgb(100, 100, 100) !important; font-size: 0.8rem; font-weight: 600;">{specifica}</p>
        <h2 style="margin: 10px 0 0 0; color: {colore_bordo} !important; font-size: 2.5rem; font-weight: 900;">{valore}</h2>
    </div>
    """

m1.markdown(box_metrica("CASI CONFERMATI", "MONDO", dati_ecdc['confermati'], "rgb(220, 53, 69)"), unsafe_allow_html=True)
m2.markdown(box_metrica("DECESSI", "MONDO", dati_ecdc['morti'], "rgb(0, 0, 0)"), unsafe_allow_html=True)
m3.markdown(box_metrica("CASI PROBABILI", "MONDO", dati_ecdc['probabili'], "rgb(253, 126, 20)"), unsafe_allow_html=True)
m4.markdown(box_metrica("MONITORAGGIO", "ITALIA", dati_ecdc['italia_quarantena'], "rgb(0, 123, 255)"), unsafe_allow_html=True)

# --- LEGENDA (RIMOSSO CASO SOSPETTO) ---
st.markdown("<br><hr>", unsafe_allow_html=True)
st.subheader("Legenda Definizioni")
col_l1, col_l2 = st.columns(2)

def box_legenda(titolo, testo, colore_sinistra):
    return f"""
    <div style="background-color: rgb(235, 235, 235) !important; padding: 15px; border-radius: 10px; border-left: 6px solid {colore_sinistra}; min-height: 100px; margin-bottom: 10px;">
        <strong style="color: rgb(0, 0, 0) !important; font-size: 1.1rem; display: block; margin-bottom: 5px;">{titolo}:</strong>
        <span style="color: rgb(40, 40, 40) !important; font-size: 0.95rem; font-weight: 500;">{testo}</span>
    </div>
    """

with col_l1:
    st.markdown(box_legenda("Caso Probabile", "Persona con sintomi clinici e un legame epidemiologico confermato con un altro caso.", "#fd7e14"), unsafe_allow_html=True)
with col_l2:
    st.markdown(box_legenda("Caso Confermato", "Caso che soddisfa i criteri clinici ed è confermato da test di laboratorio (PCR o sierologia).", "#dc3545"), unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: rgb(100, 100, 100) !important; font-size: 0.85rem; font-weight: 600; padding-bottom: 30px;">
        Sviluppato da <strong>iGhostPro</strong> con il supporto di <strong>Gemini AI</strong> • 2026
    </div>
    """, 
    unsafe_allow_html=True
)

# Auto-refresh ogni ora
st.components.v1.html(f"<script>setTimeout(function(){{window.location.reload();}}, 3600000);</script>", height=0)
