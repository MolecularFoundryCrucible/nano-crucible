# Downloading Data

## Download a dataset

`client.download()` saves the API record as `record.json` and, for datasets, downloads all associated files:

```python
# Download everything into a local directory
client.download("ds-abc123", output_dir="./downloads")
```

This creates `./downloads/ds-abc123/record.json` plus all files.

### Filtering files

```python
# Download only .dat files
client.datasets.download("ds-abc123", output_dir="./downloads", include="*.dat")

# Download everything except thumbnails
client.datasets.download("ds-abc123", output_dir="./downloads", exclude="*.png")
```

### Overwriting existing files

By default, files that already exist locally are skipped. Pass `overwrite=True` to replace them:

```python
client.datasets.download("ds-abc123", output_dir="./downloads", overwrite=True)
```

## Download a sample record

For samples, `client.download()` saves the API record and a list of linked datasets:

```python
client.download("sm-abc123", output_dir="./downloads")
```

## Get pre-signed download URLs

If you need direct download links (e.g., to share with collaborators or use in a script), get pre-signed URLs valid for approximately one hour:

```python
links = client.datasets.get_download_links("ds-abc123")
for link in links:
    print(link["filename"], link["url"])
```

## CLI

```bash
# Download a dataset or sample by ID (type auto-detected)
crucible download DATASET_ID

# Specify output directory
crucible download DATASET_ID --output-dir ./my-data

# Filter by filename pattern
crucible download DATASET_ID --include "*.dm4"

# Skip downloading files (record.json only)
crucible download DATASET_ID --no-files

# Overwrite existing files
crucible download DATASET_ID --overwrite

# List files without downloading
crucible dataset list-files DATASET_ID
```

## Caching

The CLI caches downloaded files so repeated downloads don't re-fetch from the server. Manage the cache with:

```bash
crucible cache show                        # view cache size and top files
crucible cache clear --older-than 30       # remove entries not accessed in 30 days
crucible cache clear --dataset DATASET_ID  # remove a specific dataset
crucible cache clear -y                    # wipe the entire cache
```
