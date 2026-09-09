# Instrument Model

| Field | Description | Settable |
|---|---|---|
| `instrument_id` | Unique 3-to-25-character slug used to reference the instrument | create, update |
| `instrument_name` | Human-readable display name | create, update |
| `owner_orcid` | Canonical owner identifier returned by the API; deprecated as a creation input | read; deprecated for create |
| `owner` | Flexible owner identifier on create; public-safe user record on reads with owner expansion | create with an ORCID, MFID, username, or email; expanded by default on `get()` |
| `location` | Physical location (e.g. room number or building) | create, update |
| `manufacturer` | Instrument manufacturer (e.g. `"FEI"`, `"Bruker"`) | create, update |
| `model` | Manufacturer model name or number | create, update |
| `instrument_type` | Category of instrument (e.g. `"Transmission electron microscope"`) | create, update |
| `description` | Free-text description of the instrument | create, update |
| `other_id` | External identifier (e.g. facility inventory number, RRID, DOI) | create, update |
| `other_id_source` | Source of the external identifier (e.g. `"RRID"`, `"DOI"`) | create, update |
| `unique_id` | System-assigned MFID identifier | server-assigned |
| `creation_time` | When the record was created | server-assigned |
| `modification_time` | When the record was last modified | server-assigned |
| `status` | Lifecycle state: `active`, `maintenance`, or `decommissioned` | server-managed |
| `capabilities` | Optional caller-specific actions calculated for an exact response | server-assigned |

New and renamed instrument IDs must contain 3 to 25 characters. Lookup remains compatible with older IDs outside that range.

# Working with Instruments

## Creating an instrument

Instruments are shared across all projects. If an instrument with the same `instrument_id` slug already exists, `create()` returns the existing record rather than creating a duplicate.

```python
from crucible.models import Instrument

instrument = client.instruments.create(Instrument(
    instrument_id="team-i",
    instrument_name="TEAM I",
    manufacturer="FEI",
    model="Titan 80-300",
    location="72-150",
    instrument_type="Transmission electron microscope",
    description="Aberration-corrected TEM/STEM with monochromator",
    other_id="SCR_023886",
    other_id_source="RRID",
))
```

When `owner` is omitted, the authenticated human identity becomes the owner. A human platform administrator may create an instrument for another registered identity by supplying an ORCID, MFID, username, or email. Service accounts cannot create instruments, including for themselves.

## Listing instruments

```python
instruments = client.instruments.list()
for i in instruments:
    print(i["instrument_name"], i["location"])
```

Normal list operations return active instruments.
Pass `status="maintenance"` or `status="decommissioned"` to select another lifecycle state.
List owner expansion is opt-in with `include_owner=True`.

## Getting an instrument

```python
instrument = client.instruments.get("team-i")
# or by canonical MFID
instrument = client.instruments.get("0tkn2knjast3h0008nyq9zps2c")
```

Singleton retrieval expands `owner` by default as a public-safe user record containing `unique_id`, `username`, `first_name`, and `last_name`.
Pass `include_owner=False` to suppress expansion.
The canonical owner identifier remains available as `owner_orcid`.

Exact MFID and slug lookups include caller-specific `capabilities` when the server has calculated them. General lists and searches normally return `capabilities=None`, which means the guidance was not calculated rather than that every action is denied. The API remains authoritative for each mutation.

Use `instrument_id=` or `instrument_mfid=` when the intended identifier type must be explicit. Display names are not identifiers and are not accepted by the general lookup. For compatibility, an MFID-shaped value supplied as `instrument_id=` is temporarily treated as an MFID and emits a deprecation warning.

## Updating an instrument

```python
client.instruments.update("0tkn2knjast3h0008nyq9zps2c", description="Updated description", location="72-200")
```

Lifecycle changes use the dedicated status operation:

```python
client.instruments.set_status("0tkn2knjast3h0008nyq9zps2c", "maintenance")
```

Ownership is not an update field.
Preview an ownership transfer first, then repeat it with confirmation:

```python
client.instruments.transfer_ownership(
    "0tkn2knjast3h0008nyq9zps2c",
    "new-owner",
)
client.instruments.transfer_ownership(
    "0tkn2knjast3h0008nyq9zps2c",
    "new-owner",
    confirm=True,
)
```

## Managing service-account operators

Instrument administrators can inspect, add, and remove service-account operators through the instrument namespace:

```python
operators = client.instruments.list_service_accounts("0tkn2knjast3h0008nyq9zps2c")
client.instruments.bind_service_account("0tkn2knjast3h0008nyq9zps2c", "0tkvpezyz1zzf00076nahf85j4")
client.instruments.unbind_service_account("0tkn2knjast3h0008nyq9zps2c", "0tkvpezyz1zzf00076nahf85j4")
```

## Referencing instruments in datasets

Once registered, reference an instrument in datasets by its slug:

```python
from crucible.models import Dataset

dataset = client.datasets.create(dataset=Dataset(
    dataset_name="HAADF-STEM image of Au NPs",
    measurement="STEM imaging",
    instrument_id="team-i",
    project_id="MFP12345",
))
```
