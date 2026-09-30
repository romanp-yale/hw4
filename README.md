# Campus Customs storefront

React + Vite + TypeScript storefront backed by a local SQLite catalogue and a FastAPI shopping agent. The Home and About copy is original; [Yale Bulldog Blue by Campus Customs](https://yalebulldogblue.com/) was used only for context about the shop's categories and tone.

## Data source

After cloning, unpack the separately supplied data pack into this project's `data/` folder so that `data/campus_customs.db` and `data/products/` exist. The database and image directory are local-only and ignored by Git; they are not in the public repository. Product listings, prices, colors, and inventory are read from this SQLite database. If it or the backend is unavailable, the UI shows an error rather than made-up product data.

## Run locally

Use two terminals from this folder. For chat, copy `.env.example` to `.env` and replace the `PORTKEY_API_KEY` placeholder with your own Portkey key; `.env` is ignored by Git. The catalogue and account pages still run without an AI key, but chat will display a configuration error.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

On macOS or Linux, activate the Python environment with `source .venv/bin/activate`; the remaining commands are the same. Use Python 3.11+ and Node.js with npm. Keep both terminals open while using the shop.

Open `http://127.0.0.1:5173`. The Vite development server proxies `/api` to FastAPI on port 8000 by default. API documentation is at `http://127.0.0.1:8000/docs`. If port 8000 is occupied, use another backend port and set `VITE_API_TARGET` in an ignored `frontend/.env.local` to its URL before starting Vite. This workspace currently uses port 8764 because another local service occupies 8000.

## Chat configuration

The shop assistant uses PydanticAI with `gpt-6-luna` through Portkey. Set `PORTKEY_API_KEY` in your environment or an ignored `.env` in this project or a parent folder. `.env.example` shows the available settings. `PORTKEY_MODEL` defaults to `gpt-6-luna`; `PORTKEY_BASE_URL` defaults to `https://api.portkey.ai/v1`. No temperature setting is applied. Reasoning is medium for normal questions, low for brief greetings, and high for comparisons or long requests.

The chat widget posts to `/api/chat`. Its replies and product cards come from the agent and local SQLite catalogue. Signed-in conversations are saved in the local `chat_messages` table and reloaded on return; guest chat lasts for the browser session. The agent receives verified account identity and current page context, with read-only tools for catalogue, color, and size stock lookups. Agent-loop and tool outcomes append to `output/audit_trail.json` without recording raw chat or secrets. If the key, model, or database is unavailable, the widget displays the error. Product and account pages still work independently of a missing Portkey key.

Create account and Log in write to the local `users` table and use an HTTP-only cookie session. Use `COOKIE_SECURE=1` when running behind HTTPS. This version does not include checkout.
