# Demon Nawaf Bot

A standalone Telegram bot for testing the Demon Nawaf Akinator-style game. It does not connect to the main Nawaf bot or its database.

## Deploy on Zeabur

1. Import this GitHub repository into Zeabur: `omhatan6789-netizen/demon-nawaf-bot`.
2. Choose a Python service and use `python main.py` as the start command if Zeabur does not detect the `Procfile` automatically.
3. Add the environment variable `BOT_TOKEN` with the token of the new bot created through @BotFather.
4. Deploy the service.

The service exposes `/health` on the port supplied by Zeabur (or port 8080 locally).

## Optional Cloudflare solver

If Akinator blocks direct requests, configure `AKIPY_SOLVER_URL` with the URL of a FlareSolverr-compatible solver. Leave it unset for the first connection test; most games may work without a solver.

## Local run

```bash
pip install -r requirements.txt
BOT_TOKEN="your-token" python main.py
```

Never commit bot tokens or other secrets to this repository.
