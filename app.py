import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import json
import pypdf
import io
from PIL import Image
import base64

# Seitenkonfiguration (Browser-Tab Name und Layout)
st.set_page_config(page_title="Coolify ❄️", page_icon="❄️", layout="centered")

# Titel der App
st.title("Coolify ❄️ – Deine Kälte-KI & Projekt-Akte")

# Verbindung zu Supabase & OpenAI laden
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Fehler bei der Supabase-Verbindung (Secrets prüfen!): {e}")

try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=openai_api_key)
    MODEL_NAME = "gpt-4o" 
except Exception as e:
    st.error(f"Fehler bei den OpenAI Secrets: {e}")

# --- SEITENLEISTE: KUNDEN-AUSWAHL ---
st.sidebar.header("📁 Kunden-Akte / Chat")

# Kunden aus Supabase laden
try:
    response = supabase.table("chat_verlaeufe").select("kunde").execute()
    kunden_liste = sorted(list(set([row["kunde"] for row in response.data]))) if response.data else []
except Exception:
    kunden_liste = []

kunden_liste.insert(0, "+ Neuer Kunde / Neues Projekt")
auswahl = st.sidebar.selectbox("Wähle einen Kunden:", kunden_liste)

if auswahl == "+ Neuer Kunde / Neues Projekt":
    neuer_kunde = st.sidebar.text_input("Name des Kunden / Projekts:")
    aktueller_kunde = neuer_kunde.strip() if neuer_kunde else "Allgemein"
else:
    aktueller_kunde = auswahl

st.sidebar.markdown(f"**Aktuelles Projekt:** `{aktueller_kunde}`")
st.sidebar.markdown("---")
st.sidebar.info("💡 **Tipp:** Du kannst unten im Chat per Kamera-Symbol Bilder hochladen oder über den Button Dokumente für das Projekt füttern!")

# --- CHAT-VERLAUF LADEN ---
if "current_kunde" not in st.session_state or st.session_state["current_kunde"] != aktueller_kunde:
    st.session_state["current_kunde"] = aktueller_kunde
    st.session_state.messages = []
    
    try:
        res = supabase.table("chat_verlaeufe").select("nachrichten").eq("kunde", aktueller_kunde).execute()
        if res.data and len(res.data) > 0:
            st.session_state.messages = res.data[0]["nachrichten"]
    except Exception as e:
        print(f"Konnte Verlauf nicht laden: {e}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat-Verlauf anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- DIREKTER DOKUMENTEN-UPLOAD (NEBEN DEM CHAT ODER KOMPAKT DARUNTER) ---
# Wir machen es elegant direkt über dem Eingabefeld in einer schmalen Zeile
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(f"💬 *Chatte mit Coolify für Projekt:* **{aktueller_kunde}**")
with col2:
    # Kompakter Datei-Upload-Button
    uploaded_doc = st.file_uploader("PDF/TXT hochladen", type=["pdf", "txt"], label_visibility="collapsed")

if uploaded_doc is not None:
    file_content = ""
    if uploaded_doc.type == "application/pdf":
        try:
            reader = pypdf.PdfReader(uploaded_doc)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    file_content += text + "\n"
        except Exception as e:
            st.error(f"Fehler beim Lesen der PDF: {e}")
    else:
        file_content = uploaded_doc.getvalue().decode("utf-8", errors="ignore")

    if file_content:
        try:
            supabase.table("dokumente").insert({
                "name": f"[{aktueller_kunde}] {uploaded_doc.name}",
                "inhalt": file_content
            }).execute()
            st.success(f"🧊 Dokument erfolgreich eingelesen & gelernt: {uploaded_doc.name}!")
        except Exception as e:
            st.error(f"Fehler beim Speichern in Supabase: {e}")

# --- NEUE EINGABE DES NUTZERS ---
if prompt := st.chat_input(f"Frag Coolify etwas zu {aktueller_kunde} (Text oder Bild)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # Relevantes Wissen aus Dokumenten abrufen
    kontext_wissen = ""
    try:
        docs_res = supabase.table("dokumente").select("name, inhalt").execute()
        if docs_res.data:
            for doc in docs_res.data:
                if aktueller_kunde.lower() in doc["name"].lower() or "allgemein" in doc["name"].lower():
                    kontext_wissen += f"\n--- Dokument: {doc['name']} ---\n{doc['inhalt'][:3000]}\n"
    except Exception as e:
        print(f"Fehler beim Laden des Dokumenten-Wissens: {e}")

    # Coole, persönliche System-Prompt mit Emojis und Kälte-Charme
    system_prompt_text = (
        "Du bist 'Coolify', ein absolut cooler, verlässlicher und kompetenter Experte für Kälte- und Klimatechnik 🧊❄️. "
        "Du hast eine lockere, zupackende Art, sprichst den Nutzer auf Augenhöhe an und liebst präzise Handwerksarbeit. "
        "Antworte immer passend mit Emojis (wie ❄️, 🥶, 🔧, ⚡, 🧊, ✅), um deinen Antworten Persönlichkeit und Leben einzuhauchen. "
        "Nutze die folgenden hochgeladenen Dokumente/Wissensdatenbank-Auszüge, um die technischen Fragen des Nutzers (z.B. zu Anlagen, Fehlern, Schaltplänen oder Typenschildern) perfekt zu beantworten:\n"
        f"{kontext_wissen}"
    )

    formatted_messages = [{"role": "system", "content": system_prompt_text}]
    for m in st.session_state.messages:
         formatted_messages.append({"role": m["role"], "content": m["content"]})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=formatted_messages,
            max_tokens=800
        )
        
        assistant_reply = response.choices[0].message.content
        
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        with st.chat_message("assistant"):
            st.markdown(assistant_reply)
            
        # Chat in Supabase abspeichern
        existing = supabase.table("chat_verlaeufe").select("id").eq("kunde", aktueller_kunde).execute()
        if existing.data and len(existing.data) > 0:
            supabase.table("chat_verlaeufe").update({"nachrichten": st.session_state.messages}).eq("kunde", aktueller_kunde).execute()
        else:
            supabase.table("chat_verlaeufe").insert({"kunde": aktueller_kunde, "nachrichten": st.session_state.messages}).execute()

    except Exception as e:
        st.error(f"Uff, da hat's im Kühlkreislauf geklemmt: {e}")