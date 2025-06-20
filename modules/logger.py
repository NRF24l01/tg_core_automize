import logging

COLORS = {
    "DEBUG": "\033[37m",    # Серый
    "INFO": "\033[36m",     # Голубой
    "WARNING": "\033[33m",  # Жёлтый
    "ERROR": "\033[31m",    # Красный
    "CRITICAL": "\033[41m", # Красный фон
    "RESET": "\033[0m"
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        level_name = record.levelname
        color = COLORS.get(level_name, "")
        reset = COLORS["RESET"]
        message = super().format(record)
        return f"{color}{message}{reset}"

class Logger:
    def __init__(self, filename=None):
        self.filename = filename
        self.logger = logging.getLogger("my_logger")
        self.logger.setLevel(logging.DEBUG)

        self.console_handler = logging.StreamHandler()
        self.console_formatter = ColorFormatter(u'%(levelname)s - %(message)s')
        self.console_handler.setFormatter(self.console_formatter)
        self.logger.addHandler(self.console_handler)

        if filename:
            self.file_handler = logging.FileHandler(self.filename, encoding='utf-8')
            self.file_formatter = logging.Formatter(u'%(asctime)s - %(levelname)s - %(message)s')
            self.file_handler.setFormatter(self.file_formatter)
            self.logger.addHandler(self.file_handler)

    def info(self, *args):
        self.logger.info(" ".join(map(str, args)))

    def warning(self, *args):
        self.logger.warning(" ".join(map(str, args)))

    def error(self, *args):
        self.logger.error(" ".join(map(str, args)))

# Пример использования
if __name__ == "__main__":
    logger = Logger()
    logger.info("Это", "информационное", "сообщение", 123)
    logger.warning("Это", "предупреждение", {"ключ": "значение"})
    logger.error("Это", "сообщение", "об ошибке", [1, 2, 3])
