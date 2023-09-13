# -*- coding: utf-8 -*-
from __future__ import annotations
from base64 import b64encode
from enum import IntEnum
from datetime import datetime
from inspect import Parameter, signature
from json import dump as json_save, dumps as json_dump, load as json_load
from logging import (
    getLogger,
    Logger,
    Formatter,
    FileHandler,
    StreamHandler,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
    DEBUG,
)
from os import path as ospath
from pathlib import Path
from sys import path as syspath, stderr, stdout
from typing import Callable

from httpx import Client, HTTPStatusError, Response, Timeout

# * request methods * #########################################################


def trycatchcall(func: Callable) -> Callable:
    """Request / API call decorator to check positional and keyword arguments
    and catch and log invalid HTTP status codes and other occouring exceptions
    without exiting the script.

    Args:
        func (Callable): Request / API call method (below defined functions)

    Raises:
        ModuleNotFoundError: Raised if no global logger has been found.

    Returns:
        Callable: Wrapped request method / function.
    """
    globalvars = globals()
    for name, var in globalvars.items():
        if isinstance(var, Logger) and name != "Logger":
            log: Logger = var
            break
        else:
            continue
    else:
        raise ModuleNotFoundError(
            f"Couldn't find global logger instance in globals dictionary."
        )

    def wrapper(*args, **kwargs) -> Response:
        """Wrapper

        Returns:
            Response: httpx.Response object with json() method
        """
        # get the function's parameter names and their expected types
        params = signature(func).parameters
        param_types = {
            param: params[param].annotation
            for param in params
            if params[param].annotation is not Parameter.empty
        }
        # check input types
        for param, expected_type in param_types.items():
            if param in kwargs:
                if not isinstance(kwargs[param], expected_type):
                    log.debug(
                        f"Keyword argument '{param}' should be of type "
                        f"{expected_type}"
                    )
            elif args and len(args) >= params[param].position:
                arg_value = args[params[param].position - 1]
                if not isinstance(arg_value, expected_type):
                    log.debug(
                        f"Positional argument '{param}' should be of type "
                        f"{expected_type}"
                    )
        # wrap and process call
        try:
            response: Response = func(*args, **kwargs)
            response.raise_for_status()
        except HTTPStatusError as httperr:
            log.error(
                f"Got invalid HTTP status code after calling {func.__name__}: "
                f"{response.status_code} != 200 (OK) >>> {httperr}"
            )
        except Exception as err:
            log.critical(
                f"Request (API call) '{func.__name__}' couldn't processed, "
                f"cause: {err}"
            )
        else:
            log.debug(
                f"Successfully called '{func.__name__}' (API call), "
                f"Response.json() (dump): {json_dump(response.json())}"
            )

    return wrapper


@trycatchcall
def login(username: str = "apiuser", password: str = "password") -> Response:
    """Login using UG6x username and password for authentication

    NOTE: This must be performed once a day. Session token expires after 24h.

    >>> Response.status_code -> HTTP status code as int
    >>> Response.json() -> response as python dictionary (JSON object)

    Args:
        username (str, optional): UG6x API's username, defaults to "apiuser".
        password (str, optional): UH6x API's password, defaults to "password".

    Returns:
        Response: httpx.Response object with status_code attr and json() method
    """
    global client
    credentials = {"username": username.strip(), "password": password.strip()}
    response = client.post("/internal/login", json=credentials)
    if response.status_code == 200:
        dct = response.json()
        if "jwt" in dct:
            client.headers.update({"Authorization": f"Bearer {dct['jwt']}"})
    # else: # already done in @trycatchcall
    #     response.raise_for_status()

    return response


@trycatchcall
def get_devices(limit: int = 1000, offset: int = 0) -> Response:
    """Get all available devices

    >>> Response.status_code -> HTTP status code as int
    >>> Response.json() -> response as python dictionary (JSON object)

    Args:
        limit (int, optional): Max number of devices to return
            in the result-test. Defaults to 1000.
        offset (int, optional): Offset in the result-set (for pagination).
            Defaults to 0.
    """
    global client
    params = {"limit": limit, "offset": offset}
    return client.get("devices", params=params)


@trycatchcall
def get_downlink_queue(devEUI: str) -> Response:
    """Get all downlink items in the device-queue

    >>> Response.status_code -> HTTP status code as int
    >>> Response.json() -> response as python dictionary (JSON object)

    Args:
        devEUI (str): Extended unique identifier (EUI) of the device.
    """
    global client
    return client.get(f"/devices/{devEUI}/queue")


@trycatchcall
def flush_downlink_queue(devEUI: str) -> Response:
    """Flush (delete) the downlink device-queue

    >>> Response.status_code -> HTTP status code as int
    >>> Response.json() -> response as python dictionary (JSON object)

    Args:
        devEUI (str): Extended unique identifier (EUI) of the device.
    """
    global client
    return client.delete(f"/devices/{devEUI}/queue")


@trycatchcall
def queue_downlink(
    devEUI: str,
    data: str,
    *,
    fport: int = 2,
    confirmed: bool = True,
    jsonObject: dict | None = None,
    reference: str | None = None,
) -> Response:
    """Queue a downlink into downlink device-queue

    >>> Response.status_code -> HTTP status code as int
    >>> Response.json() -> response as python dictionary (JSON object)

    Args:
        devEUI (str): Extended unique identifier (EUI) of the device.
        data (str): Payload as hexdigits (downlink message).
            Base64 encoded data (plaintext, will be encrypted by server).
        fport (int, optional): Application / fuction port. Defaults to 2.
        confirmed (bool, optional): Enabled receive confirmation.
            Enables ACK flag reply. Defaults to True.
        jsonObject (Optional[dict], optional): Unknown. Defaults to None.
        reference (Optional[str], optional): Random reference
            (used on ACK notification). Defaults to None.
    """
    global config
    global client
    data = {
        "fport": fport,
        "devEUI": devEUI,
        "data": b64encode(
            data.strip().lower().encode(config["globalSettings"]["encoding"])
        ).decode(config["globalSettings"]["encoding"]),
        "confirmed": confirmed,
    }
    if isinstance(jsonObject, dict):
        data["jsonObject"] = jsonObject
    if isinstance(reference, str):
        data["reference"] = reference.strip()
    return client.post(f"/devices/{devEUI}/queue", json=data)


# * helper classes and functions * ############################################


class LogLevel(IntEnum):
    """Log level mapping

    Args:
        IntEnum (enum): Enum where members are also (and must be) integers.
    """

    def __new__(cls, value: int, phrase: str, description: str = "") -> int:
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.phrase = phrase
        obj.description = description
        return obj

    INFO = (INFO, "INFO", "Logs: INFO, WARNING, ERROR, CRITICAL")
    WARNING = (WARNING, "WARNING", "Logs: WARNING, ERROR, CRITICAL")
    ERROR = (ERROR, "ERROR", "Logs: ERROR, CRITICAL")
    CRITICAL = (CRITICAL, "CRITICAL", "Logs: CRITICAL")
    DEBUG = (DEBUG, "DEBUD", "Logs: INFO, WARNING, ERROR, CRITICAL, DEBUG")

    @staticmethod
    def get_value_by_phrase(_phrase: str, /) -> int:
        # pre-check and pre-process
        if not isinstance(_phrase, str):
            raise TypeError(
                f"Phrase must be type string {str}, not type {type(_phrase)}."
            )
        else:
            phrase = _phrase.strip().upper()
        # get corresponding value
        for level in LogLevel:
            if level.phrase == phrase:
                return level.value
        else:
            raise Exception(f"Phase '{_phrase}' does not exist.")


def _trace(_dev_eui: bool = True) -> str:
    global gw
    global dev_eui
    return (
        f"{gw['address']['host']}:{gw['address']['port']}:{dev_eui}"
        if _dev_eui
        else f"{gw['address']['host']}:{gw['address']['port']}"
    )


# ! Script Section ! ##########################################################

if __name__ == "__main__":
    # * for compability (path fix) * ##########################################
    syspath.append(ospath.abspath("."))

    # * capture run-datetime * ################################################
    DT: str = datetime.now().strftime(r"%Y-%m-%d--%H-%M-%S")  # local time

    # * load configuration and downlinks * ####################################
    with open(file="./config.json", mode="r") as json_file:
        config = json_load(fp=json_file)
        logsDir = config["loggerSettings"]["logsDir"]
        queueBackups = config["globalSettings"]["queueBackupDir"]

    # * create logger instance * ##############################################
    log: Logger = getLogger(name=ospath.basename(__file__).rsplit(".", 1)[0])
    log.setLevel(level=DEBUG)
    # define logging formatter
    formatter = Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # define and register file handler
    file_handler = FileHandler(
        filename=f"{logsDir}/{DT}.log",
        encoding=config["loggerSettings"]["encoding"],
    )
    file_handler.setLevel(level=config["loggerSettings"]["fileLogLevel"])
    file_handler.setFormatter(fmt=formatter)
    log.addHandler(hdlr=file_handler)
    log.debug(f"Initialized logger: '{log}'")
    log.debug(f"Initialized logging file handler: {file_handler}")
    # define and register stderr stream handler
    try:
        if isinstance(config["loggerSettings"]["stderrLogLevel"], str):
            stderr_handler = StreamHandler(stream=stderr)
            stderr_handler.setLevel(
                # LogLevel is defined in this file (before script section)
                level=LogLevel.get_value_by_phrase(
                    config["loggerSettings"]["stderrLogLevel"]
                )
            )
            stderr_handler.setFormatter(fmt=formatter)
            log.addHandler(hdlr=stderr_handler)
    except Exception as err:
        log.warning(
            "Couldn't initialize logging stream handler for standard error "
            "console (stderr)."
        )
        log.error(err)
    else:
        log.debug(
            "Initialized logging stream handler for standard error (stderr): "
            f"{stderr_handler}"
        )
    # define and register stdout stream handler
    try:
        if isinstance(config["loggerSettings"]["stdoutLogLevel"], str):
            stdout_handler = StreamHandler(stream=stdout)
            stdout_handler.setLevel(
                # LogLevel is defined in this file (before script section)
                level=LogLevel.get_value_by_phrase(
                    config["loggerSettings"]["stdoutLogLevel"]
                )
            )
            stdout_handler.setFormatter(fmt=formatter)
            log.addHandler(hdlr=stdout_handler)
    except Exception as err:
        log.warning(
            "Couldn't initialize logging stream handler for standard output "
            "console (stdout)."
        )
        log.error(err)
    else:
        log.debug(
            "Initialized logging stream handler for standard error (stdout): "
            f"{stderr_handler}"
        )

    # todo: validate configration file (config.json)

    # * create neccessary directories
    try:
        if not ospath.exists(config["globalSettings"]["appsBackupDir"]):
            path = Path(config["globalSettings"]["appsBackupDir"])
            path.mkdir(parents=True, exist_ok=True)
            log.debug(f"Fixed path: {path}")
        if not ospath.exists(config["globalSettings"]["deviceBackupDir"]):
            path = Path(config["globalSettings"]["deviceBackupDir"])
            path.mkdir(parents=True, exist_ok=True)
            log.debug(f"Fixed path: {path}")
        if not ospath.exists(config["globalSettings"]["queueBackupDir"]):
            path = Path(config["globalSettings"]["queueBackupDir"])
            path.mkdir(parents=True, exist_ok=True)
            log.debug(f"Fixed path: {path}")
    except Exception as err:
        log.critical(f"Couldn't fix non-existant directory: {err}")

    # predefine counters
    n_gateways = 0
    n_devices = 0
    n_downlinks = 0
    # * loop over all gateways (and devices (nested) and downlinks (nested)) *
    for gw in config["gateways"]:
        try:
            # * create global client instance * +++++++++++++++++++++++++++++++
            try:
                client = Client(
                    base_url="https://{addr}:{port}/api".format(
                        addr=gw["address"]["host"], port=gw["address"]["port"]
                    ),
                    headers=config["clientSettings"]["headers"],
                    timeout=Timeout(
                        **config["clientSettings"]["timeouts"]
                        if config["clientSettings"]["timeouts"]
                        else 5.0
                    ),
                    trust_env=config["clientSettings"]["enableEnvVars"],
                    verify=(not config["clientSettings"]["insecure"]),
                    default_encoding=config["clientSettings"]["encoding"],
                )
            except Exception as err:
                log.critical(f"Failed client initialization: {err}")
            else:
                log.debug(f"Initialized client: {client}")

            # * login and get session token for further authentication * ++++++
            response = login(
                gw["credentials"]["username"], gw["credentials"]["password"]
            )

            downlinks = gw["downlinks"]
            # * loop over downlinks per device * ++++++++++++++++++++++++++++++
            for dev_eui, downlinks in zip(downlinks, downlinks.values()):
                try:
                    dev_eui = dev_eui.strip().upper()
                    # * save queue list before processing (optional) * --------
                    if gw["downlinkSettings"]["saveQueuePreProcess"]:
                        try:
                            filepath: str = (
                                f"{queueBackups}/{DT}--{dev_eui}--PRE.json"
                            )
                            with open(file=filepath, mode="w+") as json_file:
                                dct = get_downlink_queue(dev_eui).json()
                                json_save(obj=dct, fp=json_file)
                        except Exception as err:
                            log.warning(
                                "Failed to save queue (pre) backup of "
                                f"{_trace()}: {err}"
                            )
                        else:
                            log.info(
                                "Saved queue (pre) backup of "
                                f"{_trace()} to: {filepath}"
                            )
                    # * flush queue (optional) * ------------------------------
                    if gw["downlinkSettings"]["flushQueue"]:
                        try:
                            flush_downlink_queue(dev_eui)
                        except Exception as err:
                            log.warning(
                                "Failed to erase queue of "
                                f"{_trace()}: {err}"
                            )
                        else:
                            log.info(
                                "Saved queue (pre) backup of "
                                f"{_trace()} to: {filepath}"
                            )
                    # * queue downlinks * -------------------------------------
                    for downlink in downlinks:
                        try:
                            response = queue_downlink(
                                devEUI=dev_eui,
                                data=downlink,  # .strip().lower() + base64 enc.
                                fport=gw["downlinkSettings"]["fport"],
                                confirmed=gw["downlinkSettings"]["confirmed"],
                                reference=str(n_downlinks + 1),
                            )
                            if response.status_code == 200:
                                n_downlinks += 1
                                log.debug(
                                    f"Added downlink '{downlink}' to "
                                    f"{_trace()} queue."
                                )
                            else:
                                log.error(
                                    f"Failed to add downlink '{downlink}' to "
                                    f"{_trace()} queue."
                                )
                        except Exception as err:
                            log.error(
                                f"Downlink queue error of {_trace()}: {err}"
                            )
                        else:
                            log.info(f"Queued downlinks for {_trace()}")
                    else:
                        log.debug(f"Downlink loop over without interruptions.")
                    # * save queue list after processing (optional)
                    if gw["downlinkSettings"]["saveQueuePostProcess"]:
                        try:
                            filepath = (
                                f"{queueBackups}/{DT}--{dev_eui}--POST.json"
                            )
                            with open(file=filepath, mode="w+") as json_file:
                                dct = get_downlink_queue(dev_eui).json()
                                json_save(obj=dct, fp=json_file)
                        except Exception as err:
                            log.warning(
                                "Failed to save queue (post) backup of "
                                f"{_trace()}: {err}"
                            )
                        else:
                            log.info(
                                "Saved queue (post) backup of "
                                f"{_trace()} to: {filepath}"
                            )
                except Exception as err:
                    log.critical(
                        "Unexpected error during device processing of "
                        f"{_trace()} {err}"
                    )
                else:
                    n_devices += 1
                    log.info(f"Successfully processed device {_trace()}.")
            else:
                log.debug(f"Device loop over without interruptions.")
        except Exception as err:
            log.critical(
                "Unexpected error during gateway processing "
                f"(trace: {_trace()})."
            )
        else:
            n_gateways += 1
            log.info(
                f"Successfully processed all downlinks for {_trace(False)}"
            )
    else:
        log.debug(f"Gateway loop over without interruptions.")

    # * gather statistics and log them ########################################
    try:
        n_total_gateways = len(config["gateways"])
        n_total_devices, n_total_downlinks = 0, 0
        for gw in config["gateways"]:
            n_total_devices += len(config["gateways"]["downlinks"])
            for dl in config["gateways"]["downlinks"].values():
                n_total_downlinks += len(dl)
    except Exception as err:
        log.debug(f"Failed gather statistics: {err}")
    else:
        log.info(
            f"Successfully processed {n_gateways}/{n_total_gateways} gateways."
        )
        log.info(
            f"Successfully processed {n_devices}/{n_total_devices} devices."
        )
        log.info(
            f"Successfully queued {n_downlinks}/{n_total_downlinks} downlinks."
        )

    # END
