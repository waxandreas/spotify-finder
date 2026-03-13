import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

st.set_page_config(page_title="Spotify Finder", layout="centered")
st.title("🎵 Spotify Finder")

# 1. Zugriff auf die Secrets (müssen in Streamlit Cloud hinterlegt sein)
try:
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]
except Exception:
    st.error("Fehler: Secrets nicht gefunden! Hast du sie in den Streamlit-Einstellungen eingetragen?")
    st.stop()

# 2. Authentifizierungs-Setup
auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope="playlist-read-private user-library-read",
    show_dialog=True
)

# NEU: Der moderne Weg, um URL-Parameter in Streamlit abzugreifen
query_params = st.query_params

# Falls kein "code" in der URL ist -> Login zeigen
if "code" not in query_params:
    auth_url = auth_manager.get_authorize_url()
    st.info("Willkommen! Bitte melde dich zuerst bei Spotify an.")
    
    # Dieser Button öffnet den Link automatisch korrekt
    st.link_button("Mit Spotify verbinden", auth_url, type="primary")
else:
    # 1. Authentifizierung prüfen
    if 'sp' not in st.session_state:
        try:
            code = query_params["code"]
            token_info = auth_manager.get_access_token(code)
            st.session_state.sp = spotipy.Spotify(auth=token_info['access_token'])
        except Exception as e:
            st.error("Login fehlgeschlagen. Bitte Seite neu laden.")
            st.stop()

    sp = st.session_state.sp

    # 2. Schritt: Playlists finden
    if 'all_playlists' not in st.session_state:
        st.write("### Schritt 1: Verzeichnis laden")
        if st.button("Katalog erstellen"):
            all_p = []
            with st.status("Hole Playlist-Namen von Spotify...") as status:
                results = sp.current_user_playlists(limit=50)
                all_p.extend(results['items'])
                while results['next']:
                    results = sp.next(results)
                    all_p.extend(results['items'])
                    status.write(f"Gefunden: {len(all_p)} Playlists...")
                st.session_state.all_playlists = all_p
                status.update(label="Katalog bereit!", state="complete")
            st.rerun()
        st.stop()

    # 3. Schritt: Der Sichtbare Scan
    if 'all_songs' not in st.session_state:
        st.write(f"### Schritt 2: Tiefenscan ({len(st.session_state.all_playlists)} Playlists)")
        
        if st.button("🚀 Suche jetzt starten"):
            all_songs = []
            
            # Hier ist die genaue Fortschrittsanzeige
            progress_bar = st.progress(0)
            playlist_name_display = st.empty() # Platzhalter für den Namen
            counter_display = st.empty()      # Platzhalter für die Zahl
            
            total = len(st.session_state.all_playlists)
            
            for i, pl in enumerate(st.session_state.all_playlists):
                # Update der Anzeige VOR dem Laden der Playlist
                current_num = i + 1
                playlist_name_display.markdown(f"Aktuelle Playlist: **{pl['name']}**")
                counter_display.info(f"Fortschritt: {current_num} von {total}")
                progress_bar.progress(current_num / total)
                
                try:
                    # Wir holen die Songs
                    res = sp.playlist_items(
                        pl['id'], 
                        limit=100, 
                        fields='items(track(name, external_urls, artists(name)))'
                    )
                    for item in res['items']:
                        t = item.get('track')
                        if t:
                            all_songs.append({
                                "Song": t['name'], 
                                "Artists": ", ".join([a['name'] for a in t['artists']]), 
                                "Playlist": pl['name'],
                                "Link": t['external_urls']['spotify']
                            })
                except Exception as e:
                    st.warning(f"Konnte '{pl['name']}' nicht lesen. Überspringe...")
                    continue
                
            st.session_state.all_songs = all_songs
            st.success("✅ Scan abgeschlossen!")
            st.rerun()
        st.stop()

    # 4. Schritt: Die Suche
    st.write("### 🔍 Künstler suchen")
    artist_query = st.text_input("Name eingeben (z.B. Queen):").strip().lower()

    if artist_query:
        matches = [s for s in st.session_state.all_songs if artist_query in s['Artists'].lower()]
        if matches:
            st.write(f"Gefundene Songs: {len(matches)}")
            st.dataframe(matches, use_container_width=True)
        else:
            st.warning("Kein Treffer in deiner Bibliothek.")

    if st.button("🗑️ Daten löschen / Neu scannen"):
        st.session_state.clear()
        st.rerun()
