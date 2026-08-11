# Google OAuth Setup

This checkpoint configures local Google authorization for read-only Gmail and
Google Calendar access. It does not read either service yet and cannot send,
delete, archive, label, or create external events.

## Google Cloud

1. Enable the Gmail API and Google Calendar API in the Google Cloud project.
2. Configure the OAuth consent screen and add your account as a test user while
   the app remains in Testing mode.
3. Create an OAuth client with application type **Desktop app**.
4. Put the downloaded JSON file in `backend/data/google/`. Its original
   `client_secret_...apps.googleusercontent.com.json` name is supported.

The entire `backend/data/` directory is gitignored. Never commit the credential
file or generated token.

## Local Authorization

From the `backend` directory with the virtual environment activated:

```powershell
pip install -r requirements.txt
python -m app.google_auth status
python -m app.google_auth authorize
```

The `authorize` command opens Google's consent page in the default browser and
starts a temporary loopback callback server on an available local port. On
success it writes `backend/data/google/token.json`.

Only these scopes are requested:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/calendar.readonly
```

To revoke local access, delete `backend/data/google/token.json` and revoke the
app under the Google Account third-party connections page.
