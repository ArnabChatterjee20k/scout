import logging


class SafeFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "tag"):
            record.tag = "-"
        base = super().format(record)
        # for handing error attribute
        if hasattr(record, "error") and record.error is not None:
            return f"{base} | error={record.error}"
        return base


class TaggedLogger(logging.Logger):
    def log(self, level, msg, *args, tag=None, **kwargs):
        extra = kwargs.get("extra", {})
        error = kwargs.get("error", {})
        if tag is not None:
            extra["tag"] = tag

        if error is not None:
            extra["error"] = error

        kwargs["extra"] = extra
        kwargs["error"] = error
        super().log(level, msg, *args, **kwargs)

    def info(self, msg, *args, tag=None, **kwargs):
        self.log(logging.INFO, msg, *args, tag=tag, **kwargs)

    def warning(self, msg, *args, tag=None, **kwargs):
        self.log(logging.WARNING, msg, *args, tag=tag, **kwargs)

    def error(self, msg, *args, tag=None, error=None, **kwargs):
        self.log(logging.ERROR, msg, *args, tag=tag, error=None, **kwargs)


def get_logger(name: str = "app") -> logging.Logger:
    level=logging.INFO
    logging.setLoggerClass(TaggedLogger)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setLevel(level)

    formatter = SafeFormatter(
        fmt="[%(asctime)s] | [%(levelname)s] | [%(tag)s] | %(message)s",
        datefmt="%H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger