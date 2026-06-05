# Allora

Allora is een digitale toolkit voor organisatoren die inclusiever willen werken. Het platform bevat:

- een invulbaar draaiboek per event
- checklists per inclusiethema
- inclusiethema's met uitleg en acties
- real life cases
- accountfunctionaliteit om meerdere events te bewaren

## Lokaal starten

```bash
python app_server.py
```

Open daarna:

```text
http://127.0.0.1:8001/index.html
```

## Belangrijk voor hosting

De frontend bestaat uit `index.html`, `styles.css`, `script.js` en afbeeldingen.

De accountfunctie gebruikt momenteel `app_server.py` met een lokale SQLite-database `open_event_kit.db`. Dat is goed voor prototype en lokaal testen, maar niet geschikt als permanente database op Vercel. Voor echte online gebruikersaccounts is een externe database nodig, bijvoorbeeld Supabase, Neon of Vercel Postgres.

## Aanbevolen deployment

1. Zet deze map in een GitHub repository.
2. Verbind de repository met Vercel.
3. Host de frontend via Vercel.
4. Migreer de accountfunctie naar een externe database voordat echte gebruikers het platform gebruiken.
