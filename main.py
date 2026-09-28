"""Entry point. Run the API with: python main.py"""
import uvicorn

from config.settings import settings


def main() -> None:
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
