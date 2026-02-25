# Crucible Examples

This directory contains example notebooks and data files demonstrating how to use the Crucible Python client.

## Files

### Notebooks

- **`crucible_tutorial.ipynb`** - Comprehensive tutorial covering core dataset and sample operations
- **`crucible_project_management.ipynb`** - Tutorial for project and user management (requires admin permissions)

### Data Files (`data/` directory)

- **`thermal_conductivity_data.csv`** - Example thermal conductivity measurements (10 temperature points from 273-363 K)
- **`measurement_notes.txt`** - Example measurement notes and experimental conditions
- **`xrd_pattern.csv`** - Example X-ray diffraction pattern data
- **`thermal_measurement_preview.png`** - Example thumbnail image for datasets

## Tutorial Notebooks

### Main Tutorial (`crucible_tutorial.ipynb`)

The main tutorial demonstrates all core dataset and sample operations:

1. **Setup and Configuration** - Initializing the Crucible client
2. **Creating Samples** - Creating sample records in Crucible
3. **Creating Datasets** - Creating datasets with and without files
4. **Listing Datasets** - Retrieving datasets from a project
5. **Getting Dataset Details** - Retrieving dataset metadata
6. **Updating Dataset Metadata** - Modifying scientific metadata
7. **Downloading Dataset Files** - Retrieving files from datasets
8. **Linking Sample to Dataset** - Associating samples with datasets
9. **Linking Datasets** - Creating parent-child relationships between datasets
10. **Linking Samples** - Creating parent-child relationships between samples
11. **Adding Thumbnails** - Uploading preview images for datasets

### Project Management Tutorial (`crucible_project_management.ipynb`)

The project management tutorial covers administrative operations (**requires admin API key**):

1. **Setup and Configuration** - Initializing with admin credentials
2. **Creating Projects** - Creating or getting projects
3. **Getting Project Details** - Retrieving project information
4. **Listing Projects** - Viewing all accessible projects
5. **Creating Users** - Adding new users to Crucible
6. **Getting User Details** - Retrieving user information by ORCID or email
7. **Adding Users to Projects** - Granting project access to users
8. **Getting Project Users** - Listing team members for a project

## Running the Tutorials

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
   - **For main tutorial**: Regular API key from https://crucible.lbl.gov/api/v1/user_apikey
   - **For project management tutorial**: Admin API key
   - Access to project `crucible-demo` (or update the PROJECT_ID variable)

   **Alternative (without terminal access)**: If you don't have terminal access, you can initialize the client directly in your notebook:
   ```python
   from crucible import CrucibleClient
   client = CrucibleClient(
       api_url="https://crucible.lbl.gov/api/v1",
       api_key="your-api-key-here"
   )
   ```

3. Install Jupyter:
   ```bash
   pip install jupyter
   ```

### Running

Start with the main tutorial:

```bash
cd /path/to/nano-crucible/examples
jupyter notebook crucible_tutorial.ipynb
```

For project and user management (requires admin key):

```bash
cd /path/to/nano-crucible/examples
jupyter notebook crucible_project_management.ipynb
```

Or with JupyterLab:

```bash
cd /path/to/nano-crucible/examples
jupyter lab
```

## Notes

- Both tutorials use project ID `crucible-demo` by default - make sure you have access to this project or update the `PROJECT_ID` variable
- The **project management tutorial requires admin permissions** for most operations
- All example data files are located in the `data/` subdirectory
- The notebooks create new resources (samples, datasets, projects, users) in Crucible when executed
- Resource IDs are displayed for reference - you can use `crucible open <ID>` to view them in your browser
- If running in VSCode Flatpak, you may need to set the API key as an environment variable (see notebook for details)

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
