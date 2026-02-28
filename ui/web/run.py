"""Launch the web dashboard server."""

import os

import uvicorn


def main(host: str = "0.0.0.0", port: int = 8080):
    uvicorn.run("ui.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
