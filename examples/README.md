# Crucible Examples

This directory contains example notebooks and data files demonstrating how to use the Crucible Python client.

## Files

### Notebooks

- **`crucible_tutorial.ipynb`** - Comprehensive tutorial covering all core Crucible operations

### Data Files (`data/` directory)

- **`thermal_conductivity_data.csv`** - Example thermal conductivity measurements (10 temperature points from 273-363 K)
- **`measurement_notes.txt`** - Example measurement notes and experimental conditions
- **`xrd_pattern.csv`** - Example X-ray diffraction pattern data
- **`thermal_measurement_preview.png`** - Example thumbnail image for datasets

## Tutorial Notebook

The `crucible_tutorial.ipynb` notebook demonstrates:

1. **Setup and Configuration** - Initializing the Crucible client
2. **Creating Samples** - Creating sample records in Crucible
3. **Creating Datasets** - Creating datasets with and without files
4. **Listing Datasets** - Retrieving datasets from a project
5. **Getting Dataset Details** - Retrieving dataset metadata
6. **Linking Sample to Dataset** - Associating samples with datasets
7. **Linking Datasets** - Creating parent-child relationships between datasets
8. **Linking Samples** - Creating parent-child relationships between samples
9. **Adding Thumbnails** - Uploading preview images for datasets

## Running the Tutorial

### Prerequisites

1. Install nano-crucible:
   ```bash
   pip install -e /path/to/nano-crucible
   ```

2. Configure your API credentials:
   ```bash
   crucible config init
   ```

   You'll need:
   - API Key from https://crucible.lbl.gov/api/v1/user_apikey
   - Access to project `crucible-demo`

3. Install Jupyter:
   ```bash
   pip install jupyter
   ```

### Running

```bash
cd /path/to/nano-crucible/examples
jupyter notebook crucible_tutorial.ipynb
```

Or with JupyterLab:

```bash
cd /path/to/nano-crucible/examples
jupyter lab
```

## Notes

- The tutorial uses project ID `crucible-demo` - make sure you have access to this project or update the `PROJECT_ID` variable in the notebook
- All example data files are located in the `data/` subdirectory
- The notebook creates new resources (samples, datasets) in Crucible when executed
- Resource IDs are displayed at the end of the notebook for reference

## Example Data Details

### Thermal Conductivity Data
- **Format**: CSV with temperature (K), thermal conductivity (W/m·K), and uncertainty
- **Temperature range**: 273-363 K (10 points)
- **Material**: Silicon wafer
- **Method**: 3-omega method

### XRD Pattern
- **Format**: CSV with 2-theta angle (degrees), intensity, and background counts
- **Range**: 10-80 degrees
- **Features**: Multiple peaks characteristic of crystalline structure

### Measurement Notes
- **Format**: Plain text
- **Content**: Experimental conditions, equipment details, operator notes, data processing methods

### Thumbnail Image
- **Format**: PNG (200x150 pixels)
- **Content**: Simple graphical representation of thermal conductivity data
