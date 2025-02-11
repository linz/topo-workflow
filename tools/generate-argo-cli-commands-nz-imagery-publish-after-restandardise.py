import json
import os
import subprocess
import yaml
from typing import Dict, List, Union


CATALOG_FILE = "./data/imagery/stac/catalog.json"
COMMAND = "argo submit --from wftmpl/publish-copy -n argo -f ./{0}.yaml --generate-name {1}-\n"


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


def _write_params(params: Dict[str, str], file: str) -> None:
    with open(f"./publish-{file}.yaml", "w", encoding="utf-8") as output:
        yaml.dump(
            params,
            output,
            default_flow_style=False,
            default_style='"',
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        )

def _tmp_source_edit(source: str) -> str:
    if "2193/rgb" in source:
        source = source.replace("2193/rgb", "rgb/2193")
    source = os.path.join("s3://linz-workflow-artifacts/nz-imagery/", source.strip("./")).rstrip("collection.json")
    return source

def _tmp_target_edit(target: str) -> str:
    if "2193/rgb" in target:
        target = target.replace("2193/rgb", "rgb/2193")
    return target.replace("s3://linz-workflow-artifacts/nz-imagery/", "s3://nz-imagery/")

## Uncomment if you need to retrieve the STAC files
# _run_command(["git", "clone", """git@github.com:linz/imagery""", "./data/imagery/"], None)
## Need to be logged into imagery account to get the catalog.json file
# _run_command(["s5cmd", "cp", "s3://linz-imagery/catalog.json", "./data/imagery/stac/"], None)


with open(CATALOG_FILE, encoding="utf-8") as catalog:
     catalog_json = json.loads(catalog.read())

parameter_list = []

for link in catalog_json["links"]:
    if link["rel"] == "child":
        data_errors = []
        collection_link = os.path.abspath("./data/imagery/stac/" + link["href"])
        with open(collection_link, encoding="utf-8") as collection:
            collection_json = json.loads(collection.read())
            source = _tmp_source_edit(link["href"])
            target = _tmp_target_edit(source)

            params = {
                "source": source,
                "target": target,
                "include": ".tiff?$|.json$",
                "group": "1000",
                "group-size": "100Gi",
            }

            file_name = target.split("/")[-4:-2]
            file_name = f"{file_name[0]}-{file_name[1]}"
            formatted_file_name = file_name.replace("_", "-").replace(".", "-")

            parameter_list.append(COMMAND.format(formatted_file_name, formatted_file_name))

            _write_params(params, formatted_file_name)

    with open("./publish.sh", "w") as script:
        script.write("#!/bin/bash\n\n")
        script.writelines(parameter_list)
