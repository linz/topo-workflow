import csv
from typing import Dict, List, Optional

import yaml
from linz_logger import get_log

# #######################################
# USER PARAMETERS:
# SOURCE = "s3://linz-raster-data-store/"
PARAMETERS_CSV = "./imagery-standardising-parameters-bulk-process.csv"

# #######################################

# read in enums from workflow template
with open("../workflows/imagery/standardising.yaml", "r") as f:
    workflow = yaml.load(f, Loader=yaml.loader.SafeLoader)
    for parameter in workflow["spec"]["arguments"]["parameters"]:
        if parameter["name"] == "producer":
            PRODUCERS = parameter["enum"]
        if parameter["name"] == "licensor":
            LICENSORS = parameter["enum"]
        if parameter["name"] == "scale":
            SCALES = parameter["enum"]


def _format_date(date: str) -> str:
    fd_lst = date.split("/")
    year = fd_lst[2]
    day = f"{int(fd_lst[0]):02}"
    month = f"{int(fd_lst[1]):02}"
    return f"{year}-{month}-{day}"


def _validate_licensor(licensor: str) -> Optional[str]:
    if licensor in LICENSORS:
        return licensor
    if licensor == "BOPLASS Limited":
        return "BOPLASS"
    if licensor == "Kapiti Coast District Council" or licensor == "Kapiti District Council":
        return "Kāpiti Coast District Council"
    if licensor == "The Canterbury Aerial Imagery (CAI) Consortium":
        return "Canterbury Aerial Imagery Consortium (CAI)"
    if licensor == "Hawke's Bay Local Authority Shared Services (HBLASS)":
        return "Hawke's Bay Local Authority Shared Services (HB LASS)"
    if licensor == "Central Hawkes Bay District Council":
        return "Central Hawke's Bay District Council"
    if licensor == "Thames Coromandel District Council":
        return "Thames-Coromandel District Council"
    if licensor == "Waikato Regional Aerial Photography Service (WRAPS) 2017-2019":
        return "Waikato Regional Aerial Photography Service (WRAPS)"
    if licensor == "Northland Aerial Imagery Consortium (NAIC)":
        return "Northland Aerial Imagery Consortium (NAIC)"
    if licensor == "AAM NZ Limited":
        return "AAM NZ"
    if (
        licensor == "Manawatū-Whanganui LASS Ltd-Whanganui LASS Ltd"
        or licensor == "Manawatū-Whanganui LASS Ltd"
        or licensor == "Manawatū-Whanganui LASS Ltd District Council"
    ):
        return "Manawatū-Whanganui LASS"
    if " and " in licensor:
        return licensor.replace(" and ", ";")
    return None


def _add_licensor(row: List[str], index: Dict[str, int]) -> Dict[str, str]:
    licensor = _validate_licensor(row[index["licensor"]])
    if not licensor:
        get_log().warning(
            "skipped: invalid licensor",
            licensor=row[index["licensor"]],
            source=row[index["source"]],
            title=row[index["title"]],
        )
        return {}
    elif licensor and ";" in licensor:
        return {"licensor-list": licensor, "licensor": ""}
    else:
        return {"licensor": licensor, "licensor-list": ""}


def _get_valid_producer(producer: str) -> Dict[str, str]:
    if producer in PRODUCERS:
        return {"producer": producer}
    elif producer == "NZ Aerial Mapping Ltd":
        return {"producer": "NZ Aerial Mapping"}
    elif producer == "Aerial Surveys Ltd" or producer == "Aerial Surveys Limited":
        return {"producer": "Aerial Surveys"}
    elif producer == "AAM NZ Limited":
        return {"producer": "AAM NZ"}
    elif producer == "Landpro Ltd":
        return {"producer": "Landpro"}
    elif producer == "UAV Mapping NZ Ltd":
        return {"producer": "UAV Mapping NZ"}
    return {}


def _get_valid_scale(scale: str) -> Dict[str, str]:
    if scale in SCALES:
        return {"scale": scale}
    return {}


def _index_csv(header: List[str]) -> Dict[str, int]:
    ind = {}
    ind["comment"] = header.index("Comment")
    ind["source"] = header.index("target")
    # ind["target"] = header.index("target")
    ind["scale"] = header.index("scale")
    ind["title"] = header.index("Title")
    ind["licensor"] = header.index("licensor(s)")
    ind["producer"] = header.index("producer(s)")
    ind["description"] = header.index("description")
    ind["startdate"] = header.index("start_datetime")
    ind["enddate"] = header.index("end_datetime")
    ind["basemaps"] = header.index("basemaps s3 path")
    return ind


def _add_bm_params(target: str, row: List[str], index: Dict[str, int]) -> Dict[str, str]:
    get_log().info(
        "basemaps import required",
        source=row[index["source"]],
        title=row[index["title"]],
    )
    return {
        "category": "Urban Aerial Photos",
        "name": "target".rstrip("/rgb/2193/").split("/")[-1],
        "tile-matrix": "NZTM2000Quad/WebMercatorQuad",
        "blend": "20",
        "aligned-level": "6",
        "create-pull-request": "true",
    }


def _validate_params(params: Dict[str, str], row: List[str], index: Dict[str, int]) -> bool:
    if not params["scale"]:
        get_log().warning(
            "skipped: invalid scale",
            scale=row[index["scale"]],
            source=row[index["source"]],
            title=row[index["title"]],
        )
        return False
    if not params["producer"]:
        get_log().warning(
            "skipped: invalid producer",
            producer=row[index["producer"]],
            source=row[index["source"]],
            title=row[index["title"]],
        )
        return False
    return True


def _write_params(params: Dict[str, str], file: str) -> None:
    with open(f"./{file}.yaml", "w", encoding="utf-8") as output:
        yaml.dump(
            params,
            output,
            default_flow_style=False,
            default_style='"',
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        )


def main() -> None:
    spi_list = []
    sp_list = []

    command = "argo submit ~/dev/topo-workflows/workflows/imagery/standardising-publish-import.yaml -n argo -f ./{0}.yaml --generate-name ispi-{1}-\n"

    with open(PARAMETERS_CSV, "r") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader)
        index = _index_csv(header)

        for row in reader:
            if not row[index["source"]].startswith(SOURCE):
                continue

            if row[index["comment"]] != "":
                get_log().warning(
                    "skipped: comment",
                    comment=row[index["comment"]],
                    source=row[index["source"]],
                    title=row[index["title"]],
                )
                continue

            file_name = row[index["target"]].rstrip("/rgb/2193/").split("/")[-1]
            formatted_file_name = file_name.replace("_", "-").replace(".", "-")

            params = {
                "source": row[index["source"]].rstrip("/") + "/",
                "target": row[index["target"]],
                "title": row[index["title"]],
                "description": row[index["description"]],
                "start-datetime": _format_date(row[index["startdate"]]),
                "end-datetime": _format_date(row[index["enddate"]]),
            }

            params = {**params, **_add_licensor(row, index)}
            params = {**params, **_get_valid_producer(row[index["producer"]])}
            params = {**params, **_get_valid_scale(row[index["scale"]])}

            if not _validate_params(params, row, index):
                continue

            if row[index["basemaps"]] == "":
                params = {**params, **_add_bm_params(params["target"], row, index)}
                spi_list.append(command.format(formatted_file_name, formatted_file_name))
            else:
                sp_list.append(command.format(formatted_file_name, formatted_file_name))

            _write_params(params, formatted_file_name)

    with open("standardise-publish.sh", "w") as script:
        script.write("#!/bin/bash\n\n")
        script.writelines(sp_list)

    with open("standardise-publish-import.sh", "w") as script:
        script.write("#!/bin/bash\n\n")
        script.writelines(spi_list)


main()