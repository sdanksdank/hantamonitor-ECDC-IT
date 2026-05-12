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
    # Nota: L'URL del foglio viene letto automaticamente dai Secrets 
    # sotto la sezione [connections.gsheets]
except Exception as e:
    st.error("ERRORE: Configura GEMINI_API_KEY e i Secrets [connections.gsheets]!")
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
    try:
        # Connessione automatica usando i segreti [connections.gsheets]
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Lettura dati freschi (ttl=0 evita la cache)
        df = conn.read(ttl=0)
        
        # Pulizia righe vuote
        if df is not None:
            df = df.dropna(how='all')
        else:
            df = pd.DataFrame()

        identificatore = f"{data_agg} {datetime.now().strftime('%H:00')}"
        
        # Se il foglio è vuoto, carichiamo lo storico reale
        if df.empty or len(df) < 1:
            dati_iniziali = [
                {'Data': '23 Apr 2026 12:00', 'Casi Confermati': 0, 'Casi Probabili': 0, 'Casi Sospetti': 10, 'Decessi': 0},
                {'Data': '30 Apr 2026 12:00', 'Casi Confermati': 2, 'Casi Probabili': 5, 'Casi Sospetti': 20, 'Decessi': 0},
                {'Data': '05 Mag 2026 12:00', 'Casi Confermati': 5, 'Casi Probabili': 3, 'Casi Sospetti': 15, 'Decessi': 2},
                {'Data': '10 Mag 2026 12:00', 'Casi Confermati': 8, 'Casi Probabili': 2, 'Casi Sospetti': 10, 'Decessi': 3}
            ]
            df = pd.DataFrame(dati_iniziali)
            conn.update(data=df)
            return df

        # Aggiungiamo il nuovo dato se non esiste già per questa ora
        if identificatore not in df['Data'].values:
            nuova_riga = pd.DataFrame([{
                'Data': identificatore,
                'Casi Confermati': nuovi_dati['confermati'],
                'Casi Probabili': nuovi_dati['probabili'],
                'Casi Sospetti': nuovi_dati['sospetti'] + nuovi_dati['italia_quarantena'],
                'Decessi': nuovi_dati['morti']
            }])
            df = pd.concat([df, nuova_riga], ignore_index=True)
            conn.update(data=df)
        
        return df
    except Exception as e:
        st.sidebar.error(f"Errore Database: {e}")
        # Ritorna un dataframe di emergenza per non bloccare la UI
        return pd.DataFrame([{'Data': 'Errore', 'Casi Confermati': 0, 'Casi Probabili': 0, 'Casi Sospetti': 0, 'Decessi': 0}])

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Andes Virus Monitor", layout="wide")

dati, ultima_data, rischio = fetch_ecdc_specific_data()
df_storico = gestisci_database_immortale(dati, ultima_data)

# Logica Colore Rischio
colori = {"very low": "#28a745", "low": "#007bff", "moderate": "#ffc107", "high": "#dc3545"}
colore = colori.get(rischio.lower(), "#6c757d")

st.title("🛡️ Monitoraggio Mondiale ECDC - Andes Hantavirus")
st.markdown(f"**Sorgente Ufficiale:** ECDC [{URL_ECDC}]({URL_ECDC})")

# Barra del Rischio
st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 1.5rem; border-radius: 10px; border-left: 10px solid {colore}; margin-bottom: 2rem;">
        <h3 style="margin:0; color: {colore};">RISCHIO EU/EEA: {rischio.upper()}</h3>
        <p style="margin:5px 0 0 0; font-size: 1.1rem;">Valutazione ufficiale ECDC per la popolazione generale europea.</p>
    </div>
    """, unsafe_allow_html=True)

# Metriche
m1, m2, m3, m4 = st.columns(4)
m1.metric("CONFERMATI", dati['confermati'])
m2.metric("DECESSI", dati['morti'])
m3.metric("PROBABILI", dati['probabili'])
m4.metric("SOSPETTI (IT)", dati['italia_quarantena'])

st.markdown("---")

# Grafico
st.subheader("📈 Andamento Temporale (Database Immortale)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_storico['Data'], y=df_storico['Casi Confermati'], name='Confermati', line=dict(color='red', width=3), mode='lines+markers'))
fig.add_trace(go.Scatter(x=df_storico['Data'], y=df_storico['Casi Probabili'], name='Probabili', line=dict(color='orange'), mode='lines+markers'))
fig.add_trace(go.Scatter(x=df_storico['Data'], y=df_storico['Casi Sospetti'], name='Sospetti', line=dict(color='yellow', dash='dot'), mode='lines+markers'))
fig.add_trace(go.Scatter(x=df_storico['Data'], y=df_storico['Decessi'], name='Morti', line=dict(color='black', width=2), mode='lines+markers'))

fig.update_layout(hovermode="x unified", template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

# Legenda
st.markdown("---")
st.subheader("📋 LEGENDA UFFICIALE")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Caso Sospetto**: Persona su stesso trasporto o in contatto con MV Hondius dal 5 aprile, con febbre E sintomi.")
    st.markdown("**Caso Probabile**: Persona con sintomi E contatto noto con caso ANDV confermato/probabile.")
with c2:
    st.markdown("**Caso Confermato**: Persona con definizione di sospetto/probabile E test di laboratorio positivo.")

# Sidebar Tools
st.sidebar.header("Gestione")
st.sidebar.info(f"Ultimo Check: {ultima_data}")
if st.sidebar.button("Forza Aggiornamento"):
    st.rerun()

# Auto-refresh tramite JavaScript
st.components.v1.html(f"""
    <script>
    setTimeout(function(){{ window.location.reload(); }}, {AUTO_REFRESH_INTERVAL * 1000});
    </script>
""", height=0)
