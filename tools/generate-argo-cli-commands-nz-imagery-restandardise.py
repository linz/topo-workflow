import datetime
import json
import os
import subprocess
import yaml
from dateutil import parser, tz
from typing import Dict, List, Optional, Set, Union


CATALOG_FILE = "./data/imagery/stac/catalog.json"
COMMAND = "argo submit ~/dev/topo-workflows/workflows/imagery/standardising-publish-import.yaml -n argo -f ./{0}.yaml --generate-name {1}\n"
VALID_SCALES: Set[str] = {"500", "1000", "2000", "5000", "10000", "50000"}


def _run_command(command: List[str], cwd: Union[str, None]) -> "subprocess.CompletedProcess[bytes]":
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as cpe:
        raise cpe
    return proc


def _get_scale(links: List[Dict[str, str]]) -> Optional[str]:
    scales: List[str] = []
    for link in links:
        if link["rel"] == "item":
            try:
                scale = os.path.splitext(link["href"].split("_")[1])[0]
                if scale in VALID_SCALES:
                    if scale not in scales:
                        scales.append(scale)
                else:
                    data_errors.append(f"invalid scale {scale} for file {link['href']}\n")
            except:
                data_errors.append(f"cannot retrieve scale: invalid filename format for file {link['href']}\n")
    if len(scales) != 1:
        data_errors.append(f"{len(scales)} scales found, should be only 1\n")
        return None
    return scales[0]


def _format_date(date: str) -> datetime:
    utc_tz = tz.gettz("UTC")
    nz_tz = tz.gettz("Pacific/Auckland")
    try:
        utc_time = parser.parse(date).replace(tzinfo=utc_tz)
    except parser.ParserError as err:
        data_errors.append(err)
        raise Exception(f"Not a valid date: {err}") from err
    nz_time: datetime = utc_time.astimezone(nz_tz)
    return nz_time.strftime("%Y-%m-%d")


def _add_providers(providers: List[Dict[str, str]], provider_type: str) -> Dict[str, str]:
    provider_list: List[str] = []
    for provider in providers:
        if provider_type in provider["roles"]:
            provider_list.append(provider["name"])
    if len(provider_list) > 1:
        multiple_providers = ';'.join(provider_list)
        return {f"{provider_type}-list": multiple_providers, provider_type: ""}
    elif len(provider_list) == 1:
        return {f"{provider_type}-list": "", provider_type: provider_list[0]}
    else:
        data_errors.append(f"no {provider_type} for file {link['href']}\n")
        return {}


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

def _write_errors(errors: List[str], file: str) -> None:
    with open(f"./_errors_{file}.txt", "w", encoding="utf-8") as error_file:
        error_file.write(f"{link['href']}\n\n")
        error_file.writelines(errors)

def _tmp_target_edit(target: str) -> str:
    if "2193/rgb" in target:
        target = target.replace("2193/rgb", "rgb/2193")
    return target.replace("s3://linz-imagery/", "s3://linz-workflow-artifacts/nz-imagery/")

## Uncomment if you need to retrieve the STAC files
# _run_command(["git", "clone", """git@github.com:linz/imagery""", "./data/imagery/"], None)
## Need to be logged into imagery account to get the catalog.json file
# _run_command(["s5cmd", "cp", "s3://linz-imagery/catalog.json", "./data/imagery/stac/"], None)


with open(CATALOG_FILE, encoding="utf-8") as catalog:
     catalog_json = json.loads(catalog.read())

parameter_list = []
not_valid = []

for link in catalog_json["links"]:
    if link["rel"] == "child":
        data_errors = []
        collection_link = os.path.abspath("./data/imagery/stac/" + link["href"])
        with open(collection_link, encoding="utf-8") as collection:
            collection_json = json.loads(collection.read())
            source = os.path.join("s3://linz-imagery/", link["href"].strip("./")).rstrip("collection.json")
            target = _tmp_target_edit(source)
            start_datetime = _format_date(collection_json["extent"]["temporal"]["interval"][0][0])
            end_datetime = _format_date(collection_json["extent"]["temporal"]["interval"][0][1])
            scale = _get_scale(collection_json["links"])

            params = {
                "source": source,
                "target": target,
                "collection-id": collection_json["id"],
                "title": collection_json["title"],
                "description": collection_json["description"],
                "start-datetime": start_datetime,
                "end-datetime": end_datetime,
                "scale": scale,
                "source-epsg": "2193",
                "target-epsg": "2193",
                "compression": "webp",
                "retile": "false",
                "validate": "true",
                "group": "5",
            }

            params = {**params, **_add_providers(collection_json["providers"], "licensor")}
            params = {**params, **_add_providers(collection_json["providers"], "producer")}

            file_name = target.split("/")[-4:-2]
            file_name = f"{file_name[0]}-{file_name[1]}"
            formatted_file_name = file_name.replace("_", "-").replace(".", "-")

            if data_errors:
                not_valid.append(f"# {formatted_file_name}.yaml not written to bash as further action required \n")
                _write_errors(data_errors, formatted_file_name)
            else:
                parameter_list.append(COMMAND.format(formatted_file_name, formatted_file_name))

            _write_params(params, formatted_file_name)

    with open("./standardise-publish.sh", "w") as script:
        script.write("#!/bin/bash\n\n")
        script.writelines(parameter_list)
        script.writelines("\n\n\n")
        script.writelines(not_valid)
