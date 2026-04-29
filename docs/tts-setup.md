# TTS setup

Scriptorium supports four text-to-speech backends in the EPUB reader. Each is independent — enable whichever you want by setting its key/URL in `backend/.env`. The reader's TTS panel only shows toggles for backends that are configured.

| Backend | Quality | Cost | Where it runs | Best for |
|---|---|---|---|---|
| **Browser** | low | free | the user's browser | quick listen, offline, no setup |
| **Local** | high | free after setup | one or more LAN Macs | preferred default once configured |
| **Qwen** (DashScope) | high | ~$0.0001 / char | Alibaba Cloud | when no local Mac is on |
| **ElevenLabs** | high | ~$0.0003 / char | ElevenLabs Cloud | best voice quality |

Browser TTS is always available and needs no setup. The other three are off until you provide credentials.

---

## Local TTS — Apple Silicon Mac running mlx-audio

This is the recommended primary backend if you have any Apple Silicon Mac on your LAN. It runs the same Qwen3-TTS model that DashScope hosts, but on your hardware, with no per-character cost.

### Prerequisites

- An Apple Silicon Mac (M1 or newer; Intel Macs are not supported by mlx)
- Python 3.10+ (`brew install python` if needed)
- ~2-4 GB free disk for model weights, ~3-4 GB free unified memory at inference time

### One-time install on each Mac

```bash
pip install mlx-audio
```

(Use a venv if you prefer: `python3 -m venv ~/.mlx-audio && source ~/.mlx-audio/bin/activate && pip install mlx-audio`)

### Run the server

```bash
mlx_audio.server --host 0.0.0.0 --port 9000
```

The first call to a model triggers a HuggingFace download (~1.5 GB for the 8-bit variant, ~3.5 GB for bf16). You can pre-warm it:

```bash
curl -X POST http://localhost:9000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit","input":"hello","voice":"Cherry"}' \
  --output /tmp/warmup.wav
```

### Run as a background service (recommended for always-on Macs)

So you don't have to keep a terminal open. Save this as `~/Library/LaunchAgents/com.scriptorium.mlx-audio.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.scriptorium.mlx-audio</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/mlx_audio.server</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>9000</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/mlx-audio.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mlx-audio.err</string>
</dict>
</plist>
```

(Replace `/usr/local/bin/mlx_audio.server` with the actual path — `which mlx_audio.server` to find it. If you used a venv, point at `~/.mlx-audio/bin/mlx_audio.server`.)

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.scriptorium.mlx-audio.plist
```

Check it's listening:

```bash
curl http://localhost:9000/v1/models  # should return JSON
```

### Wire into Scriptorium

In `backend/.env`:

```
LOCAL_TTS_URL=http://<mac-hostname-or-ip>:9000
LOCAL_TTS_MODEL=mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit
LOCAL_TTS_VOICE=Cherry
```

Use `.local` hostnames (Bonjour) if available — `http://mac-mini.local:9000` — or fall back to a static LAN IP. Restart `uvicorn` to pick up the change.

### Adding more Macs (the whole reason this doc exists)

`LOCAL_TTS_URL` is a **comma-separated list**, tried in order. Put your preferred / faster Mac first; the proxy falls through to the next one with a 2-second connect timeout if the preferred one is asleep.

```
LOCAL_TTS_URL=http://m3-pro.local:9000,http://mac-mini.local:9000
```

To add a third, just append:

```
LOCAL_TTS_URL=http://m3-pro.local:9000,http://m4-studio.local:9000,http://mac-mini.local:9000
```

Each Mac in the chain needs to:

1. Have `mlx-audio` installed.
2. Be running `mlx_audio.server --host 0.0.0.0 --port 9000` (or any agreed port).
3. Be reachable from the Scriptorium host on that port (firewall + network).

Restart `uvicorn` after editing `.env`.

### Picking a model variant

| Model id | Size | RAM | Quality | Mac sweet spot |
|---|---|---|---|---|
| `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit` | ~1.5 GB | 4 GB | good | M1 8 GB |
| `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16` | ~3.5 GB | 8 GB | better | M2/M3+ 16 GB+ |

If your fallback chain has a mix of memory sizes, **either** standardize on the smaller model so the Mini can serve, **or** set `LOCAL_TTS_MODEL` to the larger one and accept that the Mini will reject calls for unfamiliar models until you pre-warm it. The smaller-everywhere path is simpler.

---

## Qwen via DashScope

Cloud-hosted Qwen3-TTS, used when no local Mac is on. Get a key from Alibaba Cloud Model Studio → API-KEY → Create.

```
DASHSCOPE_API_KEY=sk-...
```

Optional overrides:

```
QWEN_TTS_MODEL=qwen3-tts-flash
QWEN_TTS_VOICE=Cherry
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com   # change to dashscope.aliyuncs.com for mainland China
```

---

## ElevenLabs

Highest-quality voices, paid per character. Free tier: ~10k chars/month. Get a key from elevenlabs.io → Profile → API Keys.

```
ELEVENLABS_API_KEY=sk_...
```

Optional overrides:

```
ELEVENLABS_MODEL=eleven_multilingual_v2
ELEVENLABS_VOICE=21m00Tcm4TlvDq8ikWAM   # Rachel
```

---

## Architecture

The browser never holds API keys. All four backends are proxied through `POST /api/v1/tts/sentence` on the Scriptorium backend. The frontend calls `GET /api/v1/tts/config` once on reader load to learn which backends are wired up; it only renders toggles for available ones. Per-sentence chunking lives in `frontend/src/lib/reader/tts.svelte.ts`; the EPUB reader hands one sentence at a time to whichever backend is selected.

For the relevant code, see:

- `backend/app/api/tts.py` — proxy + per-backend handlers (`_synth_qwen`, `_synth_elevenlabs`, `_synth_local`)
- `backend/app/config.py` — env var defaults
- `frontend/src/lib/reader/tts.svelte.ts` — controller, sentence splitting, audio playback
- `frontend/src/lib/components/EpubReader.svelte` — TTS panel UI
