from handlers import log_handler, version_handler, bot_handler
import os, sys


def main(args) -> None:
    log_handler.create_logging()
    version_handler.check_version()

    try:
        settings_file_type = int(args[1])
    except:
        settings_file_type = 0

    bot = bot_handler().create_bot(version=settings_file_type)

    bot.run(token=os.getenv("DJISSU_TOKEN"), log_handler=None)


if __name__ == "__main__":
    main(sys.argv)
