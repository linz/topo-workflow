import csv
import re
from typing import List, Dict, Tuple
import yaml
from unidecode import unidecode

PARAMETERS_CSV = "./data/elevation-argo-parameters.csv"

COMMAND = "argo submit workflows/raster/standardising-publish-elevation.yaml -n argo -f ./tools/{0}.yaml --generate-name es-{1}\n"

TARGET = "nz-elevation"

def _index_csv(header: List[str]) -> Dict[str, int]:
    ind = {}
    ind["comments"] = header.index("Comments")
    ind["licensor"] = header.index("licensor")
    ind["producer"] = header.index("producer")
    ind["startdate"] = header.index("start-datetime")
    ind["enddate"] = header.index("end-datetime")
    ind["verticalEPSG"] = header.index("vertical-datum")
    ind["horizontalEPSG"] = header.index("horizontal-datum")
    ind["source"] = header.index("source")
    ind["region"] = header.index("region")
    ind["geographic_description"] = header.index("geographic_description")
    ind["event"] = header.index("event")
    return ind


def _add_licensor(row: List[str], index: Dict[str, int]) -> Dict[str, str]:
    licensor = row[index["licensor"]]
    if ";" in licensor:
        return {"licensor_list": licensor, "licensor": ""}
    else:
        return {"licensor": licensor, "licensor_list": ""}


def _add_producer(row: List[str], index: Dict[str, int]) -> Dict[str, str]:
    producer = row[index["producer"]]
    if ";" in producer:
        return {"producer_list": producer, "producer": ""}
    else:
        return {"producer": producer, "producer_list": ""}


def _get_category(source: str) -> str:
    category = re.search(r"D[ES]M", source)
    if not category:
        return ""
    if category.group(0) == "DEM":
        return "dem"
    if category.group(0) == "DSM":
        return "dsm"

def _get_date(start_datetime: str, end_datetime: str) -> str:
    if start_datetime[0:4] == end_datetime[0:4]:
        return start_datetime[0:4]
    else:
        return f"{start_datetime[0:4]}-{end_datetime[0:4]}"
    
def _get_geo_desc_slug(geographic_description: str) -> str:
    removed = geographic_description.replace("'", "")
    removed = removed.replace("/", "")
    return unidecode(removed.lower().replace(" ", "-"))

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


def _valid_params(params: Dict[str, str]) -> Tuple[bool, str]:
    if params["comments"] != "":
        return (False, params["comments"])
    if params["category"] == "":
        return (False, params["category"])
    for param in params:
        if "TODO" in params[param]:
            return (False, "TODO Noted")
    return (True, "")


with open(PARAMETERS_CSV, "r") as csv_file:
    reader = csv.reader(csv_file)
    header = next(reader)
    index = _index_csv(header)

    parameter_list = []
    not_valid = []

    for row in reader:

        category = _get_category(row[index["source"]])
        gsd = "1m"
        target_dates = _get_date(row[index["startdate"]], row[index["enddate"]])

        if row[index["geographic_description"]] != "":
            file_name = f"{_get_geo_desc_slug(row[index['geographic_description']])}-{target_dates}-{category}-{gsd}"
        else:
            file_name = f"{row[index['region']]}-{target_dates}-{category}-{gsd}"

        params = {
            "comments": row[index["comments"]],
            "source": row[index["source"]],
            "target_bucket_name": TARGET,
            "region": row[index["region"]],
            "geographic_description": row[index["geographic_description"]],
            "event": row[index["event"]],
            "start_datetime": row[index["startdate"]],
            "end_datetime": row[index["enddate"]],
            "scale": "10000",
            "gsd": gsd,
            "source_epsg": row[index["horizontalEPSG"]],
            "target_epsg": "2193",
            "compression": "dem_lerc",
            "retile": "true",
            "validate": "false",
            "group": "5",
            "lifecycle": "completed",
            "ticket": "TDE-997",
            "category": category,
        }

        params = {**params, **_add_licensor(row, index)}
        params = {**params, **_add_producer(row, index)}

        valid = _valid_params(params)
        
        if not valid[0]:
            not_valid.append(f"# {file_name}.yaml not written to bash as further action required: {valid[1]}\n")
        else:
            parameter_list.append(COMMAND.format(file_name, file_name))

            del params["comments"]
            _write_params(params, file_name)

        with open("./standardise-publish.sh", "w") as script:
            script.write("#!/bin/bash\n\n")
            script.writelines(parameter_list)
            script.writelines("\n\n\n")
            script.writelines(not_valid)
