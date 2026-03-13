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
    scope="playlist-read-private",
    show_dialog=True
)

# NEU: Der moderne Weg, um URL-Parameter in Streamlit abzugreifen
query_params = st.query_params

# Falls kein "code" in der URL ist -> Login zeigen
if "code" not in query_params:
    auth_url = auth_manager.get_authorize_url()
    st.info("Willkommen! Bitte melde dich zuerst bei Spotify an.")
    
    # HTML/CSS für den originalen Spotify-Look
    spotify_button_html = f"""
    <a href="{auth_url}" target="_blank" style="text-decoration: none;">
        <div style="
            background-color: #1DB954;
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            text-align: center;
            font-weight: bold;
            font-family: sans-serif;
            display: inline-block;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            Mit Spotify verbinden
        </div>
    </a>
    """
    st.markdown(spotify_button_html, unsafe_allow_html=True)
else:
    # 3. Token abrufen und Spotify-Client starten
    try:
        code = query_params["code"]
        token_info = auth_manager.get_access_token(code)
        sp = spotipy.Spotify(auth=token_info['access_token'])
        
        st.success("Erfolgreich eingeloggt!")
        
        # Suchmaske
        artist_query = st.text_input("Welchen Künstler suchst du in deinen Playlists?", placeholder="z.B. Queen")
        
        if artist_query:
            with st.spinner(f"Durchsuche deine Playlists nach '{artist_query}'..."):
                found_tracks = []
                playlists = sp.current_user_playlists()
                
                while playlists:
                    for pl in playlists['items']:
                        # Tracks der Playlist laden
                        results = sp.playlist_tracks(pl['id'])
                        tracks = results['items']
                        while results['next']:
                            results = sp.next(results)
                            tracks.extend(results['items'])
                        
                        # Filtern
                        for item in tracks:
                            track = item.get('track')
                            if track:
                                for artist in track['artists']:
                                    if artist_query.lower() in artist['name'].lower():
                                        found_tracks.append({
                                            "Song": track['name'],
                                            "Playlist": pl['name'],
                                            "Link": track['external_urls']['spotify']
                                        })
                    
                    if playlists['next']:
                        playlists = sp.next(playlists)
                    else:
                        playlists = None

                # Ergebnisse anzeigen
                if found_tracks:
                    st.write(f"Gefundene Songs: {len(found_tracks)}")
                    st.table(found_tracks)
                else:
                    st.warning("Nichts gefunden.")
                    
    except Exception as e:
        st.error("🚨 Ein Fehler ist aufgetreten:")
        st.exception(e) # Das zeigt uns den VOLLSTÄNDIGEN Fehlercode an
        if st.button("Sitzung zurücksetzen"):
            st.query_params.clear()
            st.rerun()
