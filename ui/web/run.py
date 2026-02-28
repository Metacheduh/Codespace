"""Launch the web dashboard server."""

import uvicorn


def main(host: str = "127.0.0.1", port: int = 8080):
    uvicorn.run("ui.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
