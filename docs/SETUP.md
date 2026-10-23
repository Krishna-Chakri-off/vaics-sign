# Setup (Windows PowerShell)
Backend
```
cd CMS\CMS-Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # set SECRET_KEY; optionally SMTP_* (Amazon SES)
python -m app.seed            # fresh demo DB with demo users (RESETS data – skip on a real DB)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Frontend
```
cd CMS\CMS-Frontend
npm install                   # installs pdfjs-dist
npm run dev -- --port 5175
```
Open http://localhost:5175 . Demo login: manager@vaics.com / Demo@123 (admin@vaics.com / Demo@123 sees all org documents).
If you open signer links from another device, set `SIGN_PUBLIC_BASE_URL` (backend) to the frontend address and `VITE_API_URL` (frontend) to the backend address.
Tests: `cd CMS-Backend; python -m pytest -q`. Build: `cd CMS-Frontend; npm run build`.
