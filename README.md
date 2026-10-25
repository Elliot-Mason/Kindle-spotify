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

## Running Natively on a Jailbroken Kindle (No PC Needed)

You can run this Spotify player directly on your Kindle with **zero external PC or server running**. The Kindle will connect to Wi-Fi, communicate with the Spotify Web API, and render album art and touch controls on-device.

### Prerequisites
1. **Jailbroken Kindle Paperwhite 1** (FW 5.6.1.1 or similar).
2. **KUAL** (Kindle Unified Application Launcher) installed.
3. **Python 3** installed on Kindle (install NiLuJe's `python3` package via MRPI or KUAL from the MobileRead forum).

### Installation Steps
1. Perform the initial Spotify OAuth authentication on your PC once (steps 1 & 2 above) to generate your authorized `config.json` containing your refresh token.
2. Connect your Kindle to your computer via USB.
3. Copy this entire folder into the Kindle's `extensions` directory:
   ```
   [Kindle USB Root]
     └── extensions/
         └── spotify/              <-- Copy this repo here
             ├── config.xml
             ├── menu.json
             ├── bin/launcher.sh
             ├── server.py
             ├── kindle.html
             └── config.json       (containing your Spotify tokens)
   ```
4. Safely eject and unplug the USB cable.

### Launching on the Kindle
1. On your Kindle home screen, tap **KUAL**.
2. Select **Spotify Kindle** &rarr; tap **Start (Standalone On-Device)**.
3. The launcher will automatically:
   - Prevent screensaver/sleep timeout (`preventScreenSaver = 1`).
   - Launch `python3 server.py` in the background on `127.0.0.1:5050`.
   - Open the Kindle Experimental Browser directly to `http://127.0.0.1:5050/kindle`.
4. Your Spotify player will now run live with interactive touch controls completely standalone!

### Stopping the App
Open **KUAL** &rarr; **Spotify Kindle** &rarr; **Stop App & Re-enable Sleep**.

---

## Testing in Kindle Simulator

You can test this app inside [Kindle-simulator](https://github.com/Elliot-Mason/Kindle-simulator):
```bash
python /path/to/Kindle-simulator/server.py --app .
```

---

## Architecture

```
Kindle-spotify/
├── config.xml              # KUAL extension manifest for jailbroken Kindle
├── menu.json               # KUAL on-device menu definition
├── bin/
│   └── launcher.sh         # On-device background daemon & browser launcher
├── kindle-app.json         # Plugin manifest for Kindle-simulator
├── kindle.html             # High-contrast ES5 Spotify player with touch controls
├── server.py               # Pure-Python Spotify OAuth & REST API proxy
├── config.example.json     # Configuration template
├── .gitignore              # Ignores local tokens and caches
└── README.md
```
