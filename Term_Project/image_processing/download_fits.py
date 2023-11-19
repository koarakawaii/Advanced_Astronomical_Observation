#!/usr/bin/env python3.10

from __future__ import print_function
from googleapiclient.http import MediaIoBaseDownload

import os.path
import io

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES            = ['https://www.googleapis.com/auth/drive']
storage_root_path = "./FITS_SDSS_Elliptical_Galaxy"
over_write_flag   = False

image_info_dict   = { "SDSS_2258+0017": {"storage_folder_name": "SDSS_2258+0017_raw",
                                         "search_by": "filter",
                                         "filter": ["B","V","I","R"],
                                         "key_word": {"B":[["B"]], "V":[["V"]], "I":[["I"]], "R":[["R"]]},
                                         "google_folder_id": {"B":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "V":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "I":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "R":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE"}
                                         },
                      "SA114"         : {"storage_folder_name": "standard_star_SA114_raw",
                                         "search_by": "filter",
                                         "filter": ["I","R"],
                                         "key_word": {"I":[["I"]], "R":[["R"]]},
                                         "google_folder_id": {"I":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "R":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE"}
                                        },
                      "Flat"          : {"storage_folder_name": "flat_field",
                                         "search_by": "filter",
                                         "key_word": {"B":[["B"]], "V":[["V"]], "I":[["I"]], "R":[["R"]]},
                                         "filter": ["B","V","I","R"],
                                         "google_folder_id": {"B":"1TXYkCja7nj3UDsIYCiZ5S0cVGETGa9Q1", "V":"1TXYkCja7nj3UDsIYCiZ5S0cVGETGa9Q1", "I":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "R":"1vA_0X9mcD8doiTnWPeW9cxA72ebsXnNE", "I": "15qsVT5HT4zKQiukXvFCVp7F4aUtThRca", "R": "15qsVT5HT4zKQiukXvFCVp7F4aUtThRca"},
                                         },
                      "Bias"          : {"storage_folder_name": "bias_field",
                                         "search_by": "temperature",
                                         "temperature": ["-5degC", "-10degC", "-15degC"],
                                         "key_word": {"-5degC":[[]], "-10degC":[[]], "-15degC":[[]]},
                                         "google_folder_id": {"-5degC": "1uLojY8sqqAFPM556jLqYOZEseDKn6v4W", "-10degC": "1ERogZTgRZmXboGAoc5rRp7Wby4zJ6YpV", "-15degC": "1VGNqpLV8ApmBDZdAJzLGGtQ2jFG0ZiJO"}
                                        },
                      "Dark"          : {"storage_folder_name": "dark_field",
                                         "search_by": "temperature",
                                         "temperature": ["-5degC", "-10degC", "-15degC"],
                                         "key_word": {"-5degC": [["5min"]], "-10degC":[["10sec"],["5min"],["8min"]], "-15degC":[["20sec"],["5min"]]},
                                         "google_folder_id": {"-5degC": "1v7j8zEBOmAxBQOpTN-oAjQ3fc055Pjgj", "-10degC": "1zgMZWYU8KNm06S_U1vS4Y81_uSuXqUHf", "-15degC": "1J_pyyusX4vb3R83sphobvPYUI_imCbv4"}
                                        }
                    }

# Note: folder_id can be parsed from the shared link
def listFiles(service, folder_id, name_keyword_list):
    listOfFiles = []

    query_string = ["and name contains '%s'"%name_keyword for name_keyword in name_keyword_list]
    query_string = " ".join(query_string)
    query_string = "'%s' in parents and mimeType='application/octet-stream'"%folder_id + " " + query_string  # common mimeType are summarized here: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
#    print(query_string)

    # Get list of jpg files in shared folder
    page_token = None
    while True:
        response = service.files().list(
            q=query_string,
            fields="nextPageToken, files(id, name)",
#            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            includeItemsFromAllDrives=True, 
            supportsAllDrives=True
        ).execute()

        for file in response.get('files', []):
            listOfFiles.append(file)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    return listOfFiles

def downloadFiles(service, storage_path, listOfFiles):
    # Download all jpegs
    for fileID in listOfFiles:
        request  = service.files().get_media(fileId=fileID['id'])
        filename = storage_path+ '/' + fileID['name']
        if not over_write_flag and os.path.isfile(filename):
            print("%s exists!! Pass!!"%str(fileID['name']))
            continue
          
        fh = io.FileIO(filename, 'wb')
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print("Downloading..." + str(fileID['name']))

def main():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)

        # Call the Drive v3 API
        for image_type, info_dict in image_info_dict.items():
            for search_key in info_dict[info_dict["search_by"]]:
                 list_of_key_word_list  = info_dict["key_word"][search_key]
                 google_drive_folder_id = info_dict["google_folder_id"][search_key]
                 for key_word_list in list_of_key_word_list:
                     file_list    = listFiles(service, google_drive_folder_id, [".fit"] + [image_type] + key_word_list)
#                     print(file_list)
                     if search_key not in key_word_list:
                        storage_path = "%s/%s/%s/%s"%(storage_root_path, info_dict["storage_folder_name"], search_key, "_".join(key_word_list)) 
                     else:
                        storage_path = "%s/%s/%s"%(storage_root_path, info_dict["storage_folder_name"], "_".join(key_word_list)) 
                     #print(storage_path)
                     if not os.path.exists("%s"%storage_path):
                         try:
                             os.makedirs("%s"%storage_path)
                         except:
                             raise RuntimeError("Folder %s cannot be creat!!"%storage_path)
                     downloadFiles(service, storage_path, file_list)

    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
