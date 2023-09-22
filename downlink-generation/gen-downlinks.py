from datetime import datetime
from json import dump as json_dump, dumps
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
from re import compile as compile_regex_pattern
from sys import stderr, stdout
from typing import Any, Dict, List, Optional, Tuple

from pandas import DataFrame, read_excel, Series
from yaml import SafeLoader as YAMLSafeLoader, load as yaml_load

from _types import SteamTrapTypes


def import_yaml_config(filepath: str | Path) -> Dict[str, Any]:
    """Import yaml configuration file.

    Args:
        filepath (str | Path): Absolute or relative filepath to yaml file.

    """
    with open(file=filepath, mode="r") as yaml_file:
        return yaml_load(stream=yaml_file, Loader=YAMLSafeLoader)


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


def import_xlsx_tables(
    filepath: str = "./conf-table.xlsx",
    sheet1: str = "Conf-Table",
    sheet2: str = "P-T-Table",
) -> Tuple[DataFrame, DataFrame]:
    """Import decision params and pre-process column names.

    Args:
        filepath (str, optional): Absolute or relative filepath to xlsx file.
            Defaults to "./conf-table.xlsx".
        sheet1 (str, optional): Decision params table sheet name.
            Defaults to "Conf-Table".
        sheet2 (str, optional): Pressure-Temperature-Table sheet name.
            Defaults to "P-T-Table".

    Returns:
        Tuple[DataFrame, DataFrame]: Both sheets as pandas.DataFrame's.
    """
    pattern = compile_regex_pattern(
        r"\[.*?\]|\(.*?\)|\{.*?\}|<.*?>|[^a-z0-9\s\-]"  # A-Z not required ...
    )
    df1: DataFrame = read_excel(
        filepath.strip(),
        sheet_name=sheet1.strip(),
        skiprows=1,
        index_col="index",
        engine="openpyxl",
    )
    _columns: List[str] = []
    for col in df1.columns:
        _col = col.strip().replace(" ", "-").lower()  # ... cause lowering here
        _col = pattern.sub("", _col)
        _col = _col.strip("-")
        _columns.append(_col)
    else:
        df1.columns = _columns
    df2 = read_excel(
        filepath.strip(),
        sheet_name=sheet2.strip(),
        skiprows=0,
        index_col="index",
        engine="openpyxl",
    )
    df2.drop(["Id", "P [psog]", "T [K]", "T [°F]"], axis=1, inplace=True)
    df2.columns = ["p-bar", "t-celsius"]

    return df1, df2


def import_xlsx_specs(filepath: str = "./template.xlsx") -> DataFrame:
    """Import and pre-process input specifications / params.

    Args:
        filepath (str, optional): Absolute or relative filepath.
            Defaults to "./template.xlsx".

    Returns:
        DataFrame: pandas.DataFrame
    """
    global log
    global config
    df: DataFrame = read_excel(
        filepath.strip(),
        skiprows=config["input"]["skiprows"],
        index_col=None,
        engine="openpyxl",
    )
    expected_columns = [
        "deveui",
        "server",
        "steam-trap-type",
        "mounting-type",
        "hardware-model",
        "dn",
        "differential-pressure",
        "application",
        "condensate-load",
    ]
    pattern = compile_regex_pattern(
        r"\[.*?\]|\(.*?\)|\{.*?\}|<.*?>|(\d+)|[^a-z\s\-]"  # A-Z not required
    )
    _columns: List[str] = []
    unexpected_columns: List[str] = []
    for col in df.columns:
        _col = col.strip().replace(" ", "-").lower()
        _col = pattern.sub("", _col)
        _col = _col.strip("-")
        if _col in expected_columns:
            _columns.append(_col)
        else:
            log.debug(f"Got unexpected column: {col}")
            unexpected_columns.append(col)
    else:
        df.drop(unexpected_columns, axis=1, inplace=True)
        df.columns = _columns
        # todo: check mandantory columns based on configured server in config.yaml
        return df


def tohex(value: int, zpad: Optional[int] = None) -> str:
    """Convert integer value to (optional paded) hex-string.

    Args:
        value (int): Integer value to convert.
        zpad (Optional[int], optional): Hex-string length. Defaults to None.
            If hex-string has less hex-digits, zero-padding will be applied.

    Returns:
        str: Hex-digits as hex-string without '0x' prefix.
    """
    l = len(hex(value)[:2])
    if zpad is None:
        zpad = l if (l % 2 == 0) else l + 1
    elif isinstance(zpad, int):
        if l > zpad:
            raise ValueError(
                "Zero-padding 'zpad' can't be smaller as number of hex-digits. "
                f"zpad = {zpad} < {l} = length"
            )
    else:
        raise TypeError(
            f"Zero-padding 'zpad' must be type integer {int} or {None}, "
            f"not type {type(zpad)}."
        )

    return f"{value:0{zpad}x}"


def build_downlinks(row: Series, pressure: int | float, dn: int) -> List[str]:
    """Build ordered downlink list for MSB configuration.

    Args:
        row (Series): Matched parameter row.
        pressure (int | float): Corresponding differential pressure.
        dn (int): Nominal pipe size.


        reset_counters (bool, optional): Whenever to reset warn and error
            counters. Defaults to True.

    Returns:
        List[str]: List with hex-strings of hex-digits representing LoRa
            downlinks for device configuration.
    """
    global log
    global config
    global pt_table
    downlinks = []

    # set the minimal uplink frequency to speed-up the configuration process
    downlinks.append(tohex(0x01000000 | 149, 8))  # math.ceil(1.4828 / 0.01)

    # set the steam-trap-type
    stidx = SteamTrapTypes.get_member_by_description(
        row["steam-trap-type"]
    ).value  # steam-trap-type index
    downlinks.append(f"0a5{stidx}")

    # set the saturated steam temperature
    pt_idx = (pt_table["p-bar"] - pressure).abs().idxmin()
    P, T = pt_table.loc[pt_idx, "p-bar"], pt_table.loc[pt_idx, "t-celsius"]
    downlinks.append(f"82{tohex(T, 2)}")

    # set noise thresholds
    downlinks.append(f"830{stidx}00{tohex(row['tv'], 2)}")  # TV (noise)
    downlinks.append(f"830{stidx}01{tohex(row['lv'], 2)}")  # LV (noise)

    # set steam-loss thresholds and corresponding steam-loss values
    c = (
        4 if stidx == SteamTrapTypes.UNA.value and dn >= 40 else 1
    )  # correction
    downlinks.append(f"8d0{stidx}00{tohex(row['slth0'], 2)}".lower())  # SLTh0
    downlinks.append(
        f"8d0{stidx}01{tohex(row['slval0']*c, 2)}".lower()
    )  # SLVal0
    downlinks.append(f"8d0{stidx}02{tohex(row['slth1'], 2)}")  # SLTh1
    downlinks.append(f"8d0{stidx}03{tohex(row['slval1']*c, 2)}")  # SLVal1
    downlinks.append(f"8d0{stidx}04{tohex(row['slth2'], 2)}")  # SLTh2
    downlinks.append(f"8d0{stidx}05{tohex(row['slval2']*c, 2)}")  # SLVal2

    # set counters thresholds
    downlinks.append(f"8402{tohex(36, 4)}")  # WarnCntThDef
    downlinks.append(f"8502{tohex(72, 4)}")  # ErrCntThDef

    # reset counters and set uplink frequency back to desired sample period
    if config["downlinks"]["resetErrorCounters"]:
        downlinks.append(f"04fc")  # counters reset
    downlinks.append(
        tohex(0x01000000 | config["downlinks"]["uplinkFrequency"], 8)
    )

    return downlinks


if __name__ == "__main__":
    # * fix work directory * ##################################################
    workdir = Path("downlink-generation")
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

    # initialize logger
    log = init_logger()
    log.debug(f"Imported config: {dumps(config)}")

    # * import look-up tables * ###############################################
    try:
        msb_config_params, pt_table = import_xlsx_tables(
            filepath=config["lookup"]["workbook"],
            sheet1=config["lookup"]["sheet1"],
            sheet2=config["lookup"]["sheet2"],
        )  # use defaults
    except Exception as err:
        log.error(
            "Couldn't import xlsx look-up tables "
            f"(decision params and PT-table), cause: {err}"
        )
    else:
        log.debug(f"Imported xlsx look-up tables.")
        # print(msb_config_params.head())
        # print(pt_table.head())

    # * import custom user specified params * #################################
    try:
        # todo: print and log a warning if template.xlsx is beeing used
        df = import_xlsx_specs(
            config["input"]["filepath"]
            if pathfx.isfile(config["input"]["filepath"])
            else "./template.xlsx"
        )
    except Exception as err:
        log.error(
            "Couldn't import user defined msb specifications xlsx-table, "
            f"cause: {err}"
        )
    else:
        log.debug(
            f"Imported user defined msb specifications xlsx-table."
        ) if pathfx.isfile(config["input"]["filepath"]) else log.warning(
            "Imported './template.xlsx' specifications, cause couldn't find "
            "the specified input file."
        )
        # print(df.head())

    # * match decision params and retrieve corresponding configuration values *
    match_params = [
        "steam-trap-type",
        "mounting-type",
        "hardware-model",
        "condensate-load",
    ]

    # * downlinks generation * ################################################
    dct: Dict[str, List[Dict[str, List[str]]]] = {"server": []}

    # iteration loop over all configuration rows (devices)
    log.debug("Entering main-loop.")
    for idx, row in df.iterrows():
        # iteration loop over all pre-defined decision param look-up table
        log.debug(
            f"Processing row with index:{idx} and DevEUI:{row['deveui']}"
        )
        for _idx, _row in msb_config_params.iterrows():
            params = {"_idx": _idx}
            for param in match_params:
                if row[param] == _row[param]:  # includes type check
                    params[param] = row[param]
                else:
                    # log.debug(
                    #     "1st layer of param-matching failed (break): "
                    #     f"idx:{idx}, _idx:{_idx}"
                    # )
                    break  # if this is executed once, else will not be entered
            else:
                # additional conditions:
                # this section gets processed if the for-loop of the same level
                # gets processed without any break
                pressure = row["differential-pressure"]
                if pressure >= _row["p-min"] and pressure <= _row["p-max"]:
                    # log matched params
                    params["pressure"] = pressure
                    params["p-min"] = _row["p-min"]
                    params["p-max"] = _row["p-max"]
                    log.debug(f"Matched params: {dumps(params)}")
                    # continue processing
                    server_index = 0
                    for server in dct["server"]:
                        if row["server"] == server["address"]["host"]:
                            log.debug(
                                "adding device downlinks to existing server: "
                                f"{row['server']}"
                            )
                            # ... server already listed
                            dct["server"][server_index]["downlinks"][
                                row["deveui"]
                            ] = build_downlinks(
                                _row,  # loop-up table
                                pressure,
                                row["dn"],  # user defined input
                                config["downlinks"]["resetErrorCounters"],
                            )
                            break  # to bypass for-else block if matched
                        else:
                            server_index += 1
                    else:
                        server: str = row["server"].strip()
                        if server.startswith("http://"):
                            server = server[len("http://") :]
                        elif server.startswith("https://"):
                            server = server[len("https://") :]
                        server = row["server"].strip().split(":")
                        if len(server) == 1:
                            host = server[0]
                            # ! add other local server ports here -------------
                            if config["server"].lower() == "ug6x":
                                port = 8080
                            # ! -----------------------------------------------
                            else:
                                # fallback for non-local / cloud servers
                                port = 443
                        elif len(server) == 2:
                            host = server[0]
                            port = server[1]
                        else:
                            # todo: do not raise exception, log instead
                            raise ValueError(
                                "Server address contains to many elements: "
                                f"{len(server)}, server.split(':'): {server}"
                            )
                        log.debug(
                            f"Created new server json block: {row['server']}"
                        )
                        dct["server"].append(
                            {
                                "address": {"host": host, "port": port},
                                "credentials": {
                                    "username": "apiuser",
                                    "password": "password",
                                },
                                "downlinkSettings": {
                                    "fport": config["downlinks"]["fport"],
                                    "confirmed": config["downlinks"][
                                        "confirmed"
                                    ],
                                    "flushQueue": config["downlinks"][
                                        "flushQueue"
                                    ],
                                },
                                "downlinks": {
                                    row["deveui"]: build_downlinks(
                                        _row,
                                        pressure,
                                        config["downlinks"][
                                            "resetErrorCounters"
                                        ],
                                    )
                                },
                            }
                        )
                    # break out of looping over decision params
                    break
                else:
                    # level: pressure matching statement
                    if _idx == len(msb_config_params) - 1:
                        log.warning(
                            f"No parameter full-match for "
                            f"server:{row['server']}, device:{row['deveui']}."
                        )
        else:
            log.warning(
                f"No parameter full-match for "
                f"server:{row['server']}, device:{row['deveui']}."
            )
    else:
        log.debug(f"Finished main-loop without breaks.")

    # * save generated downlinks dictionary as json file * ####################
    with open(file=config["output"]["filepath"], mode="w+") as json_file:
        json_dump(obj=dct, fp=json_file, indent=config["output"]["indent"])
        log.info(f"Saved results as '{config['output']['filepath']}'.")

    log.info("All done.")

# * EOF * #####################################################################
