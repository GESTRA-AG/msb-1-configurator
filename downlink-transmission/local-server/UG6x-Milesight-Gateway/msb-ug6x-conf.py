# -*- coding: utf-8 -*-
from __future__ import annotations
from base64 import b64encode
from datetime import datetime
from inspect import Parameter, signature
from json import dump as json_save, dumps as json_dump, load as json_load
from logging import (
    getLogger,
    Logger,
    Formatter,
    FileHandler,
    StreamHandler,
    DEBUG,
)
from os import getcwd, chdir, path as pathfx, mkdir
from pathlib import Path
from sys import stderr, stdout
from typing import Any, Callable, Dict

from httpx import Client, HTTPStatusError, Response, Timeout
from yaml import load as yaml_load, SafeLoader as YAMLSafeLoader

# todo: skip server (continue) if authentication failed ..

# * logging methods * #########################################################


def init_logger() -> Logger:
    """Initialize global logger with file and stream handler setup

    Returns:
        Logger: Customized logger instance.
    """
    global config
    log: Logger = getLogger(name=pathfx.basename(__file__).rsplit(".", 1)[0])
    log.setLevel(level=DEBUG)
    # define and register file handler
    fmt = config["logging"]["fileHandler"]["filenameFormat"]
    if not pathfx.exists(config["logging"]["fileHandler"]["logsDirectory"]):
        mkdir(config["logging"]["fileHandler"]["logsDirectory"])
    file_handler = FileHandler(
        filename=(
            f"{config['logging']['fileHandler']['logsDirectory']}/"
            + f"{datetime.now().strftime(fmt)}.log"
        ),
        encoding=config["logging"]["encoding"],
    )
    file_handler.setLevel(level=config["logging"]["fileHandler"]["logLevel"])
    file_handler.setFormatter(
        fmt=Formatter(fmt=config["logging"]["fileHandler"]["formatter"])
    )
    log.addHandler(hdlr=file_handler)
    log.debug(f"Initialized logger: '{log}'")
    log.debug(f"Initialized logging file handler: {file_handler}")
    # define and register stream handler for stderr or stdout
    try:
        console = config["logging"]["streamHandler"]["console"]
        if console == "stdout":
            console = stdout
        elif console == "stderr":
            console = stderr
        elif console is not None:
            raise ValueError(
                f"logging:streamHandler:console must be 'stdout', 'stderr' "
                f"or null."
            )
        if console is not None:
            stream_handler = StreamHandler(stream=console)
            stream_handler.setLevel(
                level=config["logging"]["streamHandler"]["logLevel"]
            )
            stream_handler.setFormatter(
                fmt=Formatter(
                    fmt=config["logging"]["streamHandler"]["formatter"]
                )
            )
            log.addHandler(hdlr=stream_handler)
        else:
            log.debug(f"No logging stream handler defined.")
    except Exception as err:
        log.warning(f"Couldn't initialize logging stream handler: {err}")
    else:
        log.debug(
            "Initialized logging stream handler "
            f"({config['logging']['streamHandler']['console']}): "
            f"{stream_handler}"
        )
    log.debug(f"Logger setup done.")

    return log


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
    global log
    # ! logger can not be found dynamically inside the decorator because the
    # ! instance does not exist at the time of decoration is beeing processed
    # globalvars = globals()
    # for name, var in globalvars.items():
    #     if isinstance(var, Logger) and name != "Logger":
    #         log: Logger = var
    #         break
    #     else:
    #         print(var, type(var))
    #         continue
    # else:
    #     raise ModuleNotFoundError(
    #         f"Couldn't find global logger instance in globals dictionary."
    #     )

    def wrapper(*args, **kwargs) -> Response:
        """Wrapper

        Returns:
            Response: httpx.Response object with json() method
        """
        # get the function's parameter names and their expected types
        # todo: fix parameter checking
        # params = signature(func).parameters
        # param_types = {
        #     param: params[param].annotation
        #     for param in params
        #     if params[param].annotation is not Parameter.empty
        # }
        # # check input types
        # for param, expected_type in param_types.items():
        #     if param in kwargs:
        #         if not isinstance(kwargs[param], expected_type):
        #             log.debug(
        #                 f"Keyword argument '{param}' should be of type "
        #                 f"{expected_type}"
        #             )
        #     elif param in params:  # and len(args) >= params[param].position:
        #         param = params[param]
        #     if param.default == param.empty:
        #         # This is a positional argument
        #         arg_position = list(params).index(param)
        #         if arg_position < len(args) and not isinstance(
        #             args[arg_position], expected_type
        #         ):
        #             log.debug(
        #                 f"Positional argument '{param}' should be of type "
        #                 f"{expected_type}"
        #             )
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
            return response

    return wrapper


# * request methods * #########################################################


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
    convert_to_base64: bool = True,
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
        convert_to_base64 (bool, optional): Enable base64 conversion from hex.
            Defaults to True.
    """
    global config
    global client
    data = {
        "fport": fport,
        "devEUI": devEUI,
        "data": b64encode(bytes.fromhex(data.strip().lower())).decode(
            config["general"]["encoding"]
        )
        if convert_to_base64
        else data.strip().lower(),
        "confirmed": confirmed,
    }
    log.info(f"bool:{convert_to_base64}, data: {data['data']}")
    if isinstance(jsonObject, dict):
        data["jsonObject"] = jsonObject
    if isinstance(reference, str):
        data["reference"] = reference.strip()
    return client.post(f"/devices/{devEUI}/queue", json=data)


# * helper classes and functions * ############################################


def import_yaml_config(filepath: str | Path) -> Dict[str, Any]:
    """Import yaml configuration file.

    Args:
        filepath (str | Path): Absolute or relative filepath to yaml file.

    """
    with open(file=filepath, mode="r") as yaml_file:
        return yaml_load(stream=yaml_file, Loader=YAMLSafeLoader)


def _trace(_dev_eui: bool = True) -> str:
    global server
    global dev_eui
    return (
        f"{server['address']['host']}:{server['address']['port']}/{dev_eui}"
        if _dev_eui
        else f"{server['address']['host']}:{server['address']['port']}"
    )


# ! Script Section ! ##########################################################

if __name__ == "__main__":
    # * fix work directory * ##################################################
    workdir = Path("downlink-transmission/local-server/UG6x-Milesight-Gateway")
    if not getcwd().endswith(str(workdir)):
        chdir(workdir)
        # print(f"CWD: {getcwd()}")

    # * import global config * ################################################
    for file in ["./config.yaml", "./config.yml", "./config.example.yaml"]:
        if pathfx.isfile(file):
            config = import_yaml_config(filepath=file)
            break
    else:
        raise FileNotFoundError(f"Missing valid configuration yaml file.")
    # print(config)

    # * create logger instance * ##############################################
    log = init_logger()
    log.info(f"CWD: {workdir.absolute()}")

    # * load input file * #####################################################
    try:
        if pathfx.isfile(config["input"]["filepath"]):
            file = config["input"]["filepath"]
        elif pathfx.isfile("./downlinks.example.json"):
            file = "./downlinks.example.json"
            log.warning(
                "Loading './downlinks.example.json' because specified input "
                f"file couldn't be found."
            )
        else:
            log.critical(f"Couldn't load any input file.")
        with open(file=file, mode="r") as json_file:
            dct = json_load(fp=json_file)
            # todo: needs refactoring (cause config has been changed)
            # queueBackups = config["globalSettings"]["queueBackupDir"]
    except Exception as err:
        log.critical(
            f"Couldn't load input file with generated downlinks: {err}"
        )

    # todo: validate configration file (config.json)

    # * create neccessary directories
    # todo: needs refactoring (cause config has been changed)
    # try:
    #     if not pathfx.exists(config["globalSettings"]["appsBackupDir"]):
    #         path = Path(config["globalSettings"]["appsBackupDir"])
    #         path.mkdir(parents=True, exist_ok=True)
    #         log.debug(f"Fixed path: {path}")
    #     if not pathfx.exists(config["globalSettings"]["deviceBackupDir"]):
    #         path = Path(config["globalSettings"]["deviceBackupDir"])
    #         path.mkdir(parents=True, exist_ok=True)
    #         log.debug(f"Fixed path: {path}")
    #     if not pathfx.exists(config["globalSettings"]["queueBackupDir"]):
    #         path = Path(config["globalSettings"]["queueBackupDir"])
    #         path.mkdir(parents=True, exist_ok=True)
    #         log.debug(f"Fixed path: {path}")
    # except Exception as err:
    #     log.critical(f"Couldn't fix non-existant directory: {err}")

    # predefine counters
    n_gateways = 0
    n_devices = 0
    n_downlinks = 0
    # * loop over all gateways (and devices (nested) and downlinks (nested)) *
    for server in dct["server"]:
        # try: # todo: is this level required? -> fix
        # * create global client instance * +++++++++++++++++++++++++++++++
        try:
            client = Client(
                base_url="https://{addr}:{port}/api".format(
                    addr=server["address"]["host"],
                    port=server["address"]["port"],
                ),
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                timeout=Timeout(
                    **config["client"]["timeouts"]
                    if config["client"]["timeouts"]
                    else 5.0
                ),
                trust_env=config["client"]["enableEnvVars"],
                verify=(not config["client"]["insecure"]),
                default_encoding=config["client"]["encoding"],
            )
        except Exception as err:
            log.critical(f"Failed client initialization: {err}")
        else:
            log.debug(f"Initialized client: {client}")

        # * login and get session token for further authentication * ++++++
        response: Response = login(
            server["credentials"]["username"],
            server["credentials"]["password"],
        )
        if response.status_code != 200:
            log.critical(
                f"Login to server '{server}' failed. Skipping server block ..."
            )
            continue  # continue with next server

        downlinks = server["downlinks"]
        # * loop over downlinks per device * ++++++++++++++++++++++++++++++
        for dev_eui, downlinks in zip(downlinks, downlinks.values()):
            try:
                dev_eui = dev_eui.strip().upper()
                # * save queue list before processing (optional) * --------
                # todo: needs refactoring (cause config has been changed)
                # if server["downlinkSettings"]["saveQueuePreProcess"]:
                #     try:
                #         filepath: str = (
                #             f"{queueBackups}/{DT}--{dev_eui}--PRE.json"
                #         )
                #         with open(file=filepath, mode="w+") as json_file:
                #             dct = get_downlink_queue(dev_eui).json()
                #             json_save(obj=dct, fp=json_file)
                #     except Exception as err:
                #         log.warning(
                #             "Failed to save queue (pre) backup of "
                #             f"{_trace()}: {err}"
                #         )
                #     else:
                #         log.info(
                #             "Saved queue (pre) backup of "
                #             f"{_trace()} to: {filepath}"
                #         )
                # * flush queue (optional) * ------------------------------
                if server["downlinkSettings"]["flushQueue"]:
                    try:
                        flush_downlink_queue(dev_eui)
                    except Exception as err:
                        log.warning(
                            "Failed to erase queue of " f"{_trace()}: {err}"
                        )
                    else:
                        log.info(
                            "Flushed (deleted) all queued downlinks of "
                            f"{_trace()}"
                        )
                # * queue downlinks * -------------------------------------
                for downlink in downlinks:
                    try:
                        response = queue_downlink(
                            devEUI=dev_eui,
                            data=downlink,  # .strip().lower() + base64 enc.
                            fport=server["downlinkSettings"]["fport"],
                            confirmed=server["downlinkSettings"]["confirmed"],
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
                        log.error(f"Downlink queue error of {_trace()}: {err}")
                    else:
                        log.debug(
                            f"Queued downlink '{downlink}' for {_trace()}"
                        )
                else:
                    log.info(f"Queued downlinks for {_trace()}")
                # * save queue list after processing (optional)
                # todo: needs refactoring (cause config has been changed)
                # if server["downlinkSettings"]["saveQueuePostProcess"]:
                #     try:
                #         filepath = (
                #             f"{queueBackups}/{DT}--{dev_eui}--POST.json"
                #         )
                #         with open(file=filepath, mode="w+") as json_file:
                #             dct = get_downlink_queue(dev_eui).json()
                #             json_save(obj=dct, fp=json_file)
                #     except Exception as err:
                #         log.warning(
                #             "Failed to save queue (post) backup of "
                #             f"{_trace()}: {err}"
                #         )
                #     else:
                #         log.info(
                #             "Saved queue (post) backup of "
                #             f"{_trace()} to: {filepath}"
                #         )
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
    # todo: is this level required? -> fix
    # except Exception as err:
    #     log.critical(
    #         "Unexpected error during gateway processing "
    #         f"(trace: {_trace()})."
    #     )
    # else:
    #     n_gateways += 1
    #     log.info(
    #         f"Successfully processed all downlinks for {_trace(False)}"
    #     )
    else:
        log.debug(f"Gateway loop over without interruptions.")

    # * gather statistics and log them ########################################
    try:
        n_total_gateways = len(config["gateways"])
        n_total_devices, n_total_downlinks = 0, 0
        for server in config["server"]:
            n_total_devices += len(config["gateways"]["downlinks"])
            for dl in config["server"]["downlinks"].values():
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

    log.info("All done.")

    # print(get_downlink_queue(dev_eui).json())

# * EOF * #####################################################################
