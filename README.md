# Kindle Spotify (Now Playing & Touch Controller)

Turn your **Amazon Kindle Paperwhite (1st Gen, EY21)** into a dedicated Spotify Now Playing display with Floyd-Steinberg dithered album art and infrared touchscreen playback controls.

Compatible with [Kindle-simulator](https://github.com/Elliot-Mason/Kindle-simulator).

![Kindle Spotify Preview](https://raw.githubusercontent.com/Elliot-Mason/Kindle-simulator/main/docs/spotify-preview.png)

---

## Features
- **Live Track Progress & Metadata:** Song title, artist, album, live progress bar, and elapsed time.
- **Floyd-Steinberg E-Ink Dithering:** Converts full-color album covers to sharp 1-bit high-contrast black & white directly in your Kindle browser.
- **Touch Controls for Kindle:** Large, tactile buttons for **Previous Track**, **Pause / Play**, and **Next Track**.
- **Works on Unjailbroken Kindles:** Runs natively in the standard Kindle Experimental Browser (FW 5.6.1.1).

---

## Setup Instructions

### 1. Spotify Developer Account
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an App.
2. Under **Edit Settings**, add this Redirect URI:
   ```
   http://127.0.0.1:8888/callback
   ```
3. Copy your **Client ID** and **Client Secret**.

### 2. Configure & Run
1. Copy the example configuration:
   ```bash
   cp config.example.json config.json
   ```
2. Paste your `spotify_client_id` and `spotify_client_secret` into `config.json`.
3. Start the server:
   ```bash
   python server.py
   ```
4. Link your Spotify account by opening:
   ```
   http://localhost:5050/auth
   ```
   Click **1. Open Spotify Login**, agree to the permissions (includes `user-modify-playback-state` for touch controls), copy the redirected URL from your browser, and paste it into step 2 to complete the link.

### 3. Open on Your Kindle
1. On your Kindle Paperwhite home screen, tap the search bar, type `~ds` (Disable Screensaver), and press Enter.
2. Open the **Experimental Browser** and navigate to your computer's LAN IP:
   ```
   http://192.168.0.x:5050/kindle
   ```

---

## Testing in Kindle Simulator

You can test this app inside [Kindle-simulator](https://github.com/Elliot-Mason/Kindle-simulator):
```bash
python /path/to/Kindle-simulator/server.py --app .
```
