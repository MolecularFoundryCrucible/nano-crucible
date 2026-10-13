# FileOperations

Access via `client.files`. Operates on individual files by MFID.

For dataset-scoped file operations (upload, bulk download) use `client.datasets`.
For ingestion management use `client.ingestions`.

::: crucible.resources.files.FileOperations
    options:
      members:
        - get
        - list
        - download
        - get_download_link
        - request_ingestion
        - replace
        - update
        - delete
