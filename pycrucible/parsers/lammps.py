#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 10 17:22:34 2026

@author: roncofaber
"""

from .base import BaseParser

import os
import logging

logger = logging.getLogger(__name__)

#%%

def store_variable(varname, varvalue, vardict):
    vardict[varname] = varvalue
    return

class LAMMPSParser(BaseParser):

    _measurement = "LAMMPS"
    _data_format = "LAMMPS"
    _instrument_name = None

    def parse(self):
        """
        Parse LAMMPS input files and extract metadata.

        Reads LAMMPS input file, data file, and log file to extract
        simulation metadata, atomic structure, and version information.
        Generates a thumbnail visualization of the atomic structure.
        """
        # Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # Use first file as LAMMPS input
        input_file = os.path.abspath(self.files_to_upload[0])

        # Read input file to find related files
        lmp_metadata = self.read_lmp_input_file(input_file)

        # Build list of files to upload (input, data, and log files)
        files_list = [input_file]

        # Read data file
        data_file = os.path.join(lmp_metadata["root"], lmp_metadata["data_file"])
        data_file_metadata, ase_atoms = self.read_data_file(data_file)
        lmp_metadata.update(data_file_metadata)
        files_list.append(data_file)

        # Read LOG file
        log_file = os.path.join(lmp_metadata["root"], lmp_metadata["log_files"][0])
        log_file_metadata = self.read_log_file(log_file)
        lmp_metadata.update(log_file_metadata)
        # Note: log file not added to upload list by default

        # Update files to upload
        self.files_to_upload = files_list

        # Add extracted metadata
        self.add_metadata(lmp_metadata)

        # Add LAMMPS-specific keywords
        self.add_keywords(["LAMMPS", "molecular dynamics"])
        if "elements" in lmp_metadata:
            self.add_keywords(lmp_metadata["elements"])

        # Generate thumbnail visualization
        self.thumbnail = self.render_thumbnail(ase_atoms, self.mfid)

        # Note: dump files are parsed but not uploaded by default
        # They are stored in scientific_metadata for reference
    
    
    # main driver: reads input file and find relevant associated files
    @staticmethod
    def read_lmp_input_file(input_file):
        
        # initialize empty data
        data = {}
        vardict = {}
        
        # store path
        data["root"]  = os.path.dirname(input_file)
        data["input_file"] = os.path.basename(input_file)
        
        # initialize empty arrays
        data["dump_files"] = []
        data["log_files"]  = []
        
        with open(input_file, "r") as fin:
            
            for line in fin:
                
                if line.startswith("read_data"): # see dump section
                    data_file = line.split()[1]
                    data["data_file"] = data_file
                
                if line.startswith("variable"):
                    varname  = line.split()[1]
                    varvalue = line.split()[3]
                    store_variable(varname, varvalue, vardict)
                    
                if line.startswith("dump "): #those should end up into self.associated_files
                    dumpname = line.split()[5]
                    dumpname = dumpname.replace("$", "")
                    data["dump_files"].append(dumpname.format(**vardict))
                    
                if line.startswith("log "):
                    logname = line.split()[1]
                    logname = logname.replace("$", "")
                    data["log_files"].append(logname.format(**vardict))
                    
        # if no log specified use the standard one
        if not data["log_files"]:
            data["log_files"]  = ["log.lammps"]

        return data
    
    @staticmethod
    def read_data_file(data_file):
        
        try:
            import ase.io.lammpsdata
        except:
            raise ImportError("ASE needs to be installed for LMP ingestor to work!")
            
        lmp_metadata = {}

        ase_atoms = ase.io.lammpsdata.read_lammps_data(data_file)
        
        #TODO this should not stay like that --> should be a json
        # lmp_metadata["atoms"] = ase_atoms
        
        # store some info about the system to metadata
        lmp_metadata['elements'] = list(set(ase_atoms.get_chemical_symbols()))
        lmp_metadata['natoms']   = len(ase_atoms.get_chemical_symbols())
        lmp_metadata["volume"]   = ase_atoms.get_volume()

        # what else do we want from the data_file

        return lmp_metadata, ase_atoms    

    @staticmethod
    def read_log_file(log_file):

        data = {}

        # just read the first
        with open(log_file) as f:
            first_line = f.readline()
            
        data["lammps_version"] = first_line.strip()

        return data
    
    @staticmethod
    def render_thumbnail(ase_atoms, mfid: str):

        from ase.io import write
        from pycrucible.config import get_cache_dir
        import os
        import logging

        # Suppress matplotlib's verbose output
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

        # Get cache directory and create thumbnails_upload subdirectory
        cache_dir = get_cache_dir()
        thumbnail_dir = os.path.join(cache_dir, 'thumbnails_upload')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        # Create file path
        file_path = os.path.join(thumbnail_dir, f'{mfid}.png')
        
        # Make sure atoms are wrapped
        ase_atoms.wrap()
        
        # Write directly to file
        write(file_path, ase_atoms, 
              format='png',
              show_unit_cell=2, 
              scale=20, 
              maxwidth=512,
              rotation='90x,0y,90z')
        
        return file_path