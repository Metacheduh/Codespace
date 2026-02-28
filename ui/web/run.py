"""Launch the web dashboard server."""

import os

import uvicorn


def main(host: str = "0.0.0.0", port: int = None):
    # Allow port to be overridden by environment variable (e.g., for Railway)
    if port is None:
        port = int(os.environ.get("PORT", 8080))
    uvicorn.run("ui.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
