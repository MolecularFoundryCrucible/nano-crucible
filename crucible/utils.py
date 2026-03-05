
import os
import pytz
import subprocess as sp
import hashlib
from datetime import datetime

#%%

def run_shell(cmd, checkflag = True, background = False):
    """Execute a shell command and return the result.

    SECURITY NOTE: Prefer passing cmd as a list rather than a string to avoid shell injection.

    Args:
        cmd (str or list): The shell command to execute.
                          - str: Executed via shell (DEPRECATED - security risk)
                          - list: Executed directly (RECOMMENDED - secure)
        checkflag (bool): Whether to check return code and raise exception on failure. Defaults to True.
        background (bool): Whether to run the command in background. Defaults to False.

    Returns:
        subprocess.Popen or subprocess.CompletedProcess: Popen object if background=True,
        CompletedProcess object otherwise

    Examples:
        # Secure (recommended):
        run_shell(['rclone', 'copy', file_path, 'remote:/path'])

        # Insecure (deprecated):
        run_shell(f"rclone copy '{file_path}' remote:/path")  # DO NOT USE
    """
    # Determine if we should use shell based on cmd type
    use_shell = isinstance(cmd, str)

    if background:
        return sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, shell=use_shell,
                       universal_newlines=True)
    return sp.run(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, shell=use_shell,
                  universal_newlines=True, check=checkflag)


def checkhash(file):
    """Calculate SHA256 hash of a file.
    
    Args:
        file (str): Path to the file to hash
        
    Returns:
        str: Hexadecimal SHA256 hash of the file
    """
    with open(file,"rb") as f:
        fdata = f.read() 
        readable_hash = hashlib.sha256(fdata).hexdigest()
    return(readable_hash)

    
def get_tz_isoformat(timezone = "America/Los_Angeles"):
    """Get current time in ISO format for a specific timezone.
    
    Args:
        timezone (str): Timezone name (default: "America/Los_Angeles")
        
    Returns:
        str: Current time in ISO format for the specified timezone
    """
    pst= pytz.timezone(timezone)
    curr_pct_time = datetime.now(pst).isoformat()
    return(curr_pct_time)

def check_small_files(filelist):
    for f in filelist:
        if os.path.getsize(f) < 1e8:
            continue
        else:
            return False
    return True


def data2thumbnail(image) -> str:
    """Convert an image object to a path to a PNG file.

    For file paths the input is returned as-is. For in-memory objects
    (PIL, matplotlib, numpy) the image is written to a temporary file.

    Args:
        image: Image source. Accepts:
            - str or os.PathLike: path to an existing image file
            - PIL.Image.Image: PIL image object
            - matplotlib.figure.Figure: matplotlib figure
            - numpy.ndarray: array of shape (H, W) or (H, W, C)

    Returns:
        str: Absolute path to a PNG file

    Raises:
        FileNotFoundError: If image is a path but the file does not exist
        TypeError: If image type is not supported
    """
    import tempfile
    import uuid

    # Case 1: file path — return as-is after validating existence
    if isinstance(image, (str, os.PathLike)):
        path = os.path.abspath(image)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Thumbnail image not found: {path}")
        return path

    # In-memory objects: write to a temp PNG file
    thumbnail_dir = os.path.join(tempfile.gettempdir(), 'crucible_thumbnails')
    os.makedirs(thumbnail_dir, exist_ok=True)
    thumbnail_path = os.path.join(thumbnail_dir, f'{uuid.uuid4().hex}.png')

    # Case 2: PIL Image
    try:
        from PIL import Image as PILImage
        if isinstance(image, PILImage.Image):
            image.save(thumbnail_path, format='PNG')
            return thumbnail_path
    except ImportError:
        pass

    # Case 3: matplotlib Figure
    try:
        from matplotlib.figure import Figure
        if isinstance(image, Figure):
            image.savefig(thumbnail_path, format='png', bbox_inches='tight', dpi=150)
            return thumbnail_path
    except ImportError:
        pass

    # Case 4: numpy array — convert via PIL
    try:
        import numpy as np
        if isinstance(image, np.ndarray):
            from PIL import Image as PILImage
            PILImage.fromarray(image).save(thumbnail_path, format='PNG')
            return thumbnail_path
    except ImportError:
        pass

    raise TypeError(
        f"Unsupported thumbnail type: {type(image)}. "
        f"Supported types: str, Path, PIL.Image, matplotlib.Figure, numpy.ndarray"
    )







