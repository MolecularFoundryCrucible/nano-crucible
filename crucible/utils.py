import subprocess as sp
import hashlib
import pytz
from datetime import datetime

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









