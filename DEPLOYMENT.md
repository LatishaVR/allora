# Hosting via GitHub en Vercel

## Route A: snelle online preview

Gebruik deze route als je het platform snel wil tonen als prototype.

1. Maak een nieuwe GitHub repository aan, bijvoorbeeld `allora-platform`.
2. Upload/push deze projectmap naar GitHub.
3. Ga naar Vercel en kies `Add New Project`.
4. Importeer de GitHub repository.
5. Laat build settings leeg:
   - Framework preset: `Other`
   - Build command: leeg
   - Output directory: leeg
6. Deploy.

Let op: deze route host de pagina, maar de huidige accountfunctie met SQLite is niet productiegeschikt op Vercel.

## Route B: echte gebruikersaccounts

Gebruik deze route als gebruikers echt accounts moeten kunnen maken en meerdere events online moeten bewaren.

1. Zet de frontend op Vercel.
2. Vervang de lokale SQLite-database door een externe database.
3. Gebruik bijvoorbeeld:
   - Supabase voor auth + database
   - Neon/Postgres voor database met eigen auth
   - Vercel Postgres/Marketplace database
4. Zet geheime sleutels in Vercel Environment Variables.
5. Test registratie, login, event opslaan, event wisselen en draaiboek downloaden.

## Wat niet uploaden

Upload deze bestanden niet naar GitHub:

- `open_event_kit.db`
- `.env`
- `server.err.log`
- `server.out.log`
- `__pycache__/`

Ze staan daarom in `.gitignore`.
