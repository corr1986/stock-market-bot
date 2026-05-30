# Setup GitHub Actions per v3

## 1. Crea il repo GitHub

```bash
cd "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"
git init
git add .
git commit -m "feat: initial commit v3"
```

Crea repo privato su github.com, poi:
```bash
git remote add origin https://github.com/TUO_USERNAME/stock-market-bot.git
git push -u origin main
```

## 2. Aggiungi i Secrets

Su GitHub → Settings → Secrets and variables → Actions → New repository secret:

| Nome | Valore |
|------|--------|
| `GH_PAT` | Personal Access Token con permesso `repo` (github.com → Settings → Developer settings → Tokens) |
| `GROQ_API_KEY` | La tua chiave Groq |
| `ANTHROPIC_API_KEY` | La tua chiave Anthropic |
| `TELEGRAM_TOKEN` | Token del bot Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram |

## 3. Verifica che inst13f_cache.pkl sia nel repo

Il file è necessario per il 13F scoring. Deve essere committato:
```bash
git add inst13f_cache.pkl
git commit -m "chore: add 13F cache"
git push
```

## 4. Test manuale

Su GitHub → Actions → V3 Weekly Signal Selection → Run workflow
Su GitHub → Actions → V3 Hourly Tracker → Run workflow

## Schedule automatico

| Workflow | Quando | Ora Bali |
|----------|--------|----------|
| Weekly signals | Lunedì | 07:00 |
| Tracker (H1) | Lun-Ven ogni ora | 15:00–04:00 |

## Note

- `portfolio_v3.json` viene aggiornato e committato automaticamente dopo ogni run
- v1 (`portfolio.json`) NON è nel repo — rimane solo sul PC locale
- I log di ogni run sono visibili su GitHub → Actions
