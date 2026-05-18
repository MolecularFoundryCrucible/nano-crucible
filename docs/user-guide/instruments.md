# Instrument Model

| Field | Description | Settable |
|---|---|---|
| `instrument_name` | Unique name for the instrument as it will be referenced in datasets | create, update |
| `owner` | Person or group responsible for the instrument | create, update |
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

# Working with Instruments

## Creating an instrument

Instruments are shared across all projects. If an instrument with the same name already exists, `create()` returns the existing record rather than creating a duplicate.

```python
from crucible.models import Instrument

instrument = client.instruments.create(Instrument(
    instrument_name="TEAM I",
    manufacturer="FEI",
    model="Titan 80-300",
    owner="LBNL MF NCEM",
    location="72-150",
    instrument_type="Transmission electron microscope",
    description="Aberration-corrected TEM/STEM with monochromator",
    other_id="SCR_023886",
    other_id_source="RRID",
))
```

## Listing instruments

```python
instruments = client.instruments.list()
for i in instruments:
    print(i["instrument_name"], i["location"])
```

## Getting an instrument

```python
instrument = client.instruments.get(instrument_name="TEAM I")
# or by unique_id
instrument = client.instruments.get(instrument_id="if-abc123")
```

## Updating an instrument

```python
client.instruments.update("if-abc123", description="Updated description", location="72-200")
```

## Referencing instruments in datasets

Once registered, reference an instrument in datasets by name:

```python
from crucible.models import Dataset

dataset = client.datasets.create(dataset=Dataset(
    dataset_name="HAADF-STEM image of Au NPs",
    measurement="STEM imaging",
    instrument_name="TEAM I",
    project_id="MFP12345",
))
```
