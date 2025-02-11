# Tools

This folder contains single use scripts which have been used to assist in automating argo jobs.  
The scripts should be stored in this folder if they may become useful again in the future.

## generate-argo-cli-commands-elevation.py

**Date:** 14/02/2024

**Related Jira Tickets:** [TDE-783](https://toitutewhenua.atlassian.net/browse/TDE-783) [TDE-997](https://toitutewhenua.atlassian.net/browse/TDE-997)

**Description:**  
This script sets up for the automated processing of numerous elevation datasets using the argo cli.

**Instructions:**

1. Run:

```bash
cd ./tools
python3 generate-argo-cli-commands-elevation.py
```

**Output:**

- **region-year-datatype-gsd.yaml:** workflow parameters for this dataset
- **standardise-publish.sh:** bash script to 'deploy' argo workflows  
   **nb: the commented lines at the end of this file detail the datasets not run due to know issues.**

**Submitting:**

```bash
sh standardise-publish.sh
```
