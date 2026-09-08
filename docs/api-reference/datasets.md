# DatasetOperations

Access via `client.datasets`.

File operations are also available via `client.files` (by MFID) and ingestion via `client.ingestions`.

::: crucible.resources.datasets.DatasetOperations
    options:
      members:
        - get
        - list
        - count
        - search
        - create
        - update
        - add_file
        - add_remote_file
        - list_files
        - get_download_links
        - download
        - get_scientific_metadata
        - update_scientific_metadata
        - replace_scientific_metadata
        - search_metadata
        - add_thumbnail
        - get_thumbnails
        - update_thumbnail
        - delete_thumbnail
        - add_keyword
        - get_keywords
        - link_sample
        - unlink_sample
        - link
        - unlink
        - list_parents
        - list_children
        - get_access_groups
        - add_access_group
        - list_access
        - set_access
        - revoke_access
        - publish
        - unpublish
        - transfer_ownership
        - reassign_project
        - graph
