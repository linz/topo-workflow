# Topo-Imagery templates

## Contents:

- [Standardise Validate](##topo-imagery/standardise-validate)
- [Create Collection](##topo-imagery/create-collection)
- [Generate Hillshade](##topo-imagery/generate-hillshade)

## topo-imagery/standardise-validate - `tpl-ti-standardise-validate`

Template for TIFF standardisation and non-visual QA.

See [standardise_validate.py](https://github.com/linz/topo-imagery/blob/master/scripts/standardise_validate.py)

### Template usage

```yaml
- name: standardise-validate
  templateRef:
    name: tpl-ti-standardise-validate
    template: main
  arguments:
    parameters:
      - name: group_id
        value: '{{item}}'
      - name: collection_id
        value: '{{tasks.stac-setup.outputs.parameters.collection_id}}'
      - name: current_datetime
        value: '{{tasks.stac-setup.finishedAt}}'
      - name: target
        value: '{{=sprig.trimSuffix("/", tasks["get-location"].outputs.parameters.location)}}/flat/'
      - name: compression
        value: '{{= workflow.parameters.compression}}'
      - name: odr_url
        value: '{{=sprig.trim(workflow.parameters.odr_url)}}'
      - name: start_datetime
        value: '{{=sprig.trim(workflow.parameters.start_datetime)}}'
      - name: end_datetime
        value: '{{=sprig.trim(workflow.parameters.end_datetime)}}'
      - name: create_capture_area
        value: '{{=sprig.trim(workflow.parameters.create_capture_area)}}'
      - name: cutline
        value: '{{=sprig.trim(workflow.parameters.cutline)}}'
      - name: gsd
        value: '{{=sprig.trim(workflow.parameters.gsd)}}'
      - name: source_epsg
        value: '{{=sprig.trim(workflow.parameters.source_epsg)}}'
      - name: target_epsg
        value: '{{=sprig.trim(workflow.parameters.target_epsg)}}'
      - name: version_topo_imagery
        value: '{{= workflow.parameters.version_topo_imagery}}'
    artifacts:
      - name: group_data
        from: '{{ tasks.group.outputs.artifacts.output }}'
```

The Workflow caller must have the following volume:

```yaml
volumes:
  - name: ephemeral
    emptyDir: {}
```

## topo-imagery/create-collection - `tpl-ti-create-collection`

Template for creating a STAC collection from existing STAC items and asset TIFFs.
If TIFF footprint files exist, a `capture-area.geojson` output artifact will be created.

See [collection_from_items.py](https://github.com/linz/topo-imagery/blob/master/scripts/collection_from_items.py)

### Template usage

```yaml
- name: create-collection
  templateRef:
    name: tpl-ti-create-collection
    template: main
  arguments:
    parameters:
      - name: collection_id
        value: '{{tasks.stac-setup.outputs.parameters.collection_id}}'
      - name: linz_slug
        value: '{{tasks.stac-setup.outputs.parameters.linz_slug}}'
      - name: location
        value: '{{tasks.get-location.outputs.parameters.location}}'
      - name: current_datetime
        value: '{{tasks.stac-setup.finishedAt}}'
      - name: odr_url
        value: '{{=sprig.trim(workflow.parameters.odr_url)}}'
      - name: category
        value: '{{=sprig.trim(workflow.parameters.category)}}'
      - name: region
        value: '{{=sprig.trim(workflow.parameters.region)}}'
      - name: gsd
        value: '{{=sprig.trim(workflow.parameters.gsd)}}'
      - name: geographic_description
        value: '{{=sprig.trim(workflow.parameters.geographic_description)}}'
      - name: event
        value: '{{=sprig.trim(workflow.parameters.event)}}'
      - name: historic_survey_number
        value: '{{=sprig.trim(workflow.parameters.historic_survey_number)}}'
      - name: lifecycle
        value: '{{=sprig.trim(workflow.parameters.lifecycle)}}'
      - name: add_title_suffix
        value: 'true'
      - name: producer
        value: '{{workflow.parameters.producer}}'
      - name: producer_list
        value: '{{=sprig.trim(workflow.parameters.producer_list)}}'
      - name: licensor
        value: '{{workflow.parameters.licensor}}'
      - name: licensor_list
        value: '{{=sprig.trim(workflow.parameters.licensor_list)}}'
      - name: create_capture_dates
        value: 'false'
      - name: version_topo_imagery
        value: '{{= workflow.parameters.version_argo_tasks}}'
```

## topo-imagery/generate-hillshade - `tpl-create-hillshade`

Template for creating hillshades from TIFFs (DEM).  
See [generate_hillshade.py](https://github.com/linz/topo-imagery/pull/1253)
This `WorkflowTemplate` is also calling other templates in order to create the inputs of the `linz/topo-imagery/generate_hillshade.py` script:

1. `tile-index-validate` to create a list of tiles with their source TIFF files
2. `group` to split the list created into grouped tiles for parallel processing

It allows generating multiple types of hillshade from the same source TIFF files, as the `preset` parameter expects a list of hillshade presets.

### Template usage

```yaml
- name: create-hillshade
  templateRef:
    name: tpl-create-hillshade
    template: main
  arguments:
    parameters:
      - name: source
        value: 's3://nz-elevation/new-zealand/new-zealand-contour/dem_8m/2193/'
      - name: scale
        value: '50000'
      - name: group
        value: '2'
      - name: version_argo_tasks
        value: 'v4'
      - name: version_topo_imagery
        value: 'v7'
      - name: target
        value: '{{=sprig.trimSuffix("/", tasks["get-location"].outputs.parameters.location)}}/flat/'
      - name: preset
        value: '["greyscale", "igor"]'
```

The Workflow caller must have the following volume:

```yaml
volumes:
  - name: ephemeral
    emptyDir: {}
```

### Output

The hillshade TIFF files will be saved in a subdirectory for each of the `preset` within the `target` directory.
Example: `s3://linz-workflows-scratch/2025-02/03-test-hillshade-94clh/flat/igor/`
