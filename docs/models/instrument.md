# Instrument

An instrument is a registered piece of equipment in Crucible. Datasets reference instruments by name, providing a consistent way to filter and search data by the equipment that produced it.

## Notes

Instruments are shared across all projects. Before creating a new instrument, check whether it already exists:

```python
instruments = client.instruments.list()
```

If an instrument with the same name already exists, `client.instruments.create()` returns the existing record rather than creating a duplicate.

### other_id and other_id_source

Use these fields to store additional identifiers from external systems:

- A facility's internal inventory number
- A [Research Resource Identifier (RRID)](https://www.rrids.org/)
- A DOI for an instrument publication

## Example

```python
from crucible.models import Instrument

instrument = Instrument(
    instrument_name="TEAM I",
    manufacturer="FEI",
    model="Titan 80-300",
    owner="LBNL MF NCEM",
    location="72-150",
    instrument_type="Transmission electron microscope",
    description="Aberration-corrected TEM/STEM with monochromator",
    other_id="SCR_023886",
    other_id_source="RRID",
)

result = client.instruments.create(instrument)
```

Once registered, reference the instrument in datasets by name:

```python
from crucible.models import Dataset

dataset = Dataset(
    dataset_name="HAADF-STEM image of Au NPs",
    measurement="STEM imaging",
    instrument_name="TEAM I",
    project_id="MFP12345",
)
```
