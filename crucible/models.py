from pydantic import BaseModel
from typing import List, Optional

class BaseDataset(BaseModel):
    unique_id: Optional[str] = None
    dataset_name: Optional[str] = None
    public: Optional[bool] = False
    owner_user_id: Optional[int] = None
    owner_orcid: Optional[str] = None
    project_id: Optional[str] = None
    instrument_id: Optional[str] = None
    instrument_name: Optional[str] = None
    measurement: Optional[str] = None
    session_name: Optional[str] = None
    creation_time: Optional[str] = None
    data_format: Optional[str] = None
    file_to_upload: Optional[str] = None
    size: Optional[int] = None
    sha256_hash_file_to_upload: Optional[str] = None
    source_folder: Optional[str] = None
    json_link: Optional[str] = None
    
    class Config:
        from_attributes = True  

