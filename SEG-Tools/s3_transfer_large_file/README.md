# Demo for trasferring large file from break point

## File list

* `bigtera_download_file.py` for downloading file from S3 from breakpoint
* `bigtera_multipart_upload.py` for uploading file to S3 from breakpoint
* `obsync.py` for RRS to S3 from breakpoint

## Usage

### Setup environment
1. Install Python2.7
2. Install library

Run the following command in command line
```
pip install boto
pip install filechunkio
```

3. Create S3 account and  bucket in cluster

### Configuration

Change configuration in the head part of `bigtera_download_file.py`  and `bigtera_multipart_upload.py` 

### Test downloading file from breakpoint
1. Run `python bigtera_download_file.py` in command line
2. `CTRL+C` to stop downloading process
3. Run `python bigtera_download_file.py` again
4. Check downloading status 


### Test uploading file from breakpoint
1. Run `python bigtera_multipart_upload.py` in command line
2. `CTRL+C` to stop uploading process
3. Run `python bigtera_multipart_upload.py` again
4. Check uploading status 


