import io
import logging
import os
import time
from collections import namedtuple
from json import dumps
from typing import List, Dict, Union, Optional, Any, Tuple, BinaryIO, Sequence
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, urljoin

import requests
import urllib3
from requests_kerberos import HTTPKerberosAuth, OPTIONAL

# pdoc added
from pdoc import text
f = open("doco-py-wasp.md", "w")
f.write(text("py_wasp"))
f.close()


__version__ = '0.0.0'

_PATH_MAX = 4096  # No need to check strings that are longer than path_max for being a path


class SystemInfo:
    def __init__(self, system_info_record):
        """
        Wasp collection system info.
        :param system_info_record: Wasp system_info_record as a dictionary String -> String.
        """
        self._system_info = system_info_record

    @property
    def tags(self) -> List[str]:
        """
        :return: list of all defined tags names for the collection.
        """
        return list(self._system_info.keys())

    @property
    def key_tags(self) -> List[str]:
        """
        Get key tags of a collection.
        :return: mandatory tags array
        """
        return [t for t in self.tags if self._system_info[t]['isKey']]

    @property
    def mandatory_tags(self) -> List[str]:
        """
        Get mandatory tags of a collection.
        :return: mandatory tags array
        """
        return [t for t in self.tags if self._system_info[t]['isMandatory']]

    def get_default_value(self, tag) -> str:
        """
        :param tag: tag name (string).
        :return: tag default value (string).
        """
        if tag not in self.tags:
            raise ValueError('Tag: ' + tag + ' not found in system tags')
        return self._system_info[tag].get('defaultValue', None)

    def get_possible_values(self, tag) -> List[str]:
        """
        :param tag: tag name (string).
        :return: list of possible values for the specified tag.
        """
        if tag not in self.tags:
            raise ValueError('Tag: ' + tag + ' not found in system tags')
        return self._system_info[tag].get('select', None)


class ViewConfig:
    Column = namedtuple('Column', ['name', 'calculate_path'])

    def __init__(self, view_config_record):
        """
        Wasp collection view configuration.
        """
        self._columns = [ViewConfig.Column(name=p['name'], calculate_path=p['calculatePath'])
                         for p in view_config_record.get('properties', [])]

    @property
    def columns(self) -> List['ViewConfig.Column']:
        """
        :return: list of Column objects describing the columns to display.
        """
        return self._columns


class ReferenceValue:
    def __init__(self, value: Union[str, Dict], collection: str, conduit: 'Wasp' = None):
        """
        :param value: mongo id or the whole conduit record.
        :param collection:
        :param conduit:
        """
        self._collection = collection
        self._conduit = conduit
        if isinstance(value, dict):
            self._id = value['_id']
            self._record = value
        else:
            self._id = value
            self._record = None
            if conduit is None:
                raise ValueError("Record should be a dictionary.")

    def get_record(self):
        if self._record is None:
            self._record = self._conduit.find_records(collection=self._collection,
                                                      record_spec=self._id)[0]
        return self._record

    def get_entry(self):
        return {
            "type": "mongo_reference",
            "mongo_collection": self._collection,
            "mongo_id": self._id
        }

    def __str__(self):
        return "<ReferenceValue collection={} id={}>".format(self._collection, self._id)

    def __repr__(self):
        return self.__str__()


class FileValue(io.BytesIO):
    # All FileValue attributes are here:
    _attribute_white_list = (
        '__class__',
        '__dict__',  # This way we can get a full list of attributes and not only of io.Stream
        '__init__',
        '__str__',
        '__repr__',
        'name',
        'to_file',
        'file_url',
        'file_id',
        '__del__',
        '_close_on_delete',
        '_lazy_loaded_stream',
        '_file_value',
        '_file_name',
        '_conduit_api',
        '_open_stream'
    )

    def __init__(self, value, name=None, conduit=None):
        """
        Wasp record file value, used for uploading and downloading files in records.
        e.g. Record can be a dictionary in a format: { "tag_for_file": FileValue(args) }
        Interface equivalent to return value of open(file, "r", encoding="utf-8")
        Additional function "to_file" saves the file to a disk in a more memory efficient way.
        Additional property "file_id" returns a file id if FileValue is already stored in Wasp, None otherwise.
        :param value: io.Stream, path to a file, mongo id or a string that needs to be written as a file.
        :param name: optional name override for a file.
        :param conduit: Wasp to use if value is a mongo id.
        """
        super(FileValue, self).__init__()
        if value is None:
            # Not an error. We'll write None to a file as string instead.
            logging.debug('Value is None for name ' + str(name))
        self._close_on_delete = False
        self._lazy_loaded_stream = None
        self._file_value = None
        self._file_name = name
        self._conduit_api = conduit

        if hasattr(value, 'close'):
            # Value is a stream:
            self._lazy_loaded_stream = value
        else:
            # Value is a file path, string value or a mongo id
            # We'll load a stream when requested.
            self._file_value = str(value)

    def __str__(self):
        """
        Overrides default Python implementation. Returns compact string representation for visual feedback.
        """
        if self._conduit_api is not None:
            return "<FileValue name={} id={}>".format(self._file_name, self._file_value)
        else:
            return "<FileValue name={}>".format(self.name)

    def __repr__(self):
        return self.__str__()

    @property
    def name(self) -> str:
        """
        :return: Stream name.
        """
        if self._file_name is None:
            return self._open_stream.name
        return self._file_name

    @property
    def file_id(self) -> Optional[str]:
        """
        :return: mongo id if stored in Wasp, None otherwise.
        """
        if self._conduit_api is None:
            return None
        return self._file_value

    @property
    def file_url(self) -> Optional[str]:
        """
        :return: Wasp download path if stored in Wasp, None otherwise.
        """
        if self._conduit_api is None or self._conduit_api.public_url is None:
            return None
        return urljoin(self._conduit_api.public_url, 'file/' + str(self._file_value))

    def to_file(self, dir_path) -> str:
        """
        Writes a file to dir_path directory in a more memory efficient way. Use for big files.
        :param dir_path: directory where to store a file.
        :return: path to a created file.
        """
        if self._conduit_api is not None and self._lazy_loaded_stream is None:
            # TODO: Depends on conduit open / download implementations.
            # TODO: If open is fixed to avoid reading the whole stream, we can remove this.
            return self._conduit_api.download(self._file_value, dir_path, self._file_name)
        if not os.access(dir_path, os.W_OK):
            raise (Exception('FileEntry does not have write permission to ' + dir_path))
        file_path = os.path.join(dir_path, self.name)
        with open(file_path, 'wb') as f:
            f.writelines(self.readlines())
        return file_path

    def __del__(self):
        if self._close_on_delete and self._lazy_loaded_stream is not None:
            self._lazy_loaded_stream.close()

    @property
    def _open_stream(self):
        """
        Lazy loads stream values.
        :return: io.Stream.
        """
        if self._lazy_loaded_stream is None:
            if self._conduit_api is not None:
                # String is actually a mongo ID here
                self._lazy_loaded_stream = self._conduit_api.open(self._file_value)
                # Stream is managed by this object and must be closed on delete
                self._close_on_delete = True
            elif len(self._file_value) < _PATH_MAX and os.path.isfile(self._file_value):
                # Too long strings may make isfile() crash.
                self._lazy_loaded_stream = open(self._file_value, 'rb')
                # Stream is managed by this object and must be closed on delete
                self._close_on_delete = True
            elif self._file_value is not None:
                self._lazy_loaded_stream = io.StringIO(self._file_value)
                if self._file_name is not None:
                    self._lazy_loaded_stream.name = self._file_name
                self._close_on_delete = True
            else:
                raise ValueError('FileValue stream does not exists.')
        return self._lazy_loaded_stream

    def __getattribute__(self, item):
        """
        Redirects any attribute request to self._open_stream except for values in FileValue._attribute_white_list.
        :param item: attribute name.
        :return: attribute.
        """
        if item in FileValue._attribute_white_list:
            return object.__getattribute__(self, item)
        return self._open_stream.__getattribute__(item)


class Wasp:
    """
    Interface for WASP.
    Wasp Record is defined as a dictionary: tag -> value,
        where tag is a String and value can be a String, boolean, int, float or a FileValue.
    Keys and values in other formats are converted to Strings when possible.
    """

    # Values are good enough for most uses, no need to define as input.
    # Usually required only if Wasp is updating a server, which usually takes less than a second to complete.
    # But if entry is uploaded exactly in time - it will be lost if not reattempted.
    _RETRY_DELAY = 4  # Retry to upload / download after _RETRY_DELAY seconds
    _RETRY_ATTEMPTS = 4  # Retry to upload / download _RETRY_ATTEMPTS times

    def __init__(self,
                 server_urls: Optional[Union[str, List[str]]] = None,
                 upload_only_urls: Optional[List[str]] = None):
        """
        :param server_urls: server urls with ports as a list or a as a single value.
        :param upload_only_urls: server urls for uploads in case they are different from downloads.
        """
        if server_urls is None:
            server_urls = []
        elif not isinstance(server_urls, list):
            server_urls = [server_urls]
        self._download_urls = [url if str(url).startswith('http') else 'http://' + str(url)
                               for url in server_urls if url]
        if upload_only_urls is None or len(upload_only_urls) == 0:
            upload_only_urls = self._download_urls
        elif not isinstance(upload_only_urls, list):
            upload_only_urls = [upload_only_urls]
        self._upload_urls = [url if str(url).startswith('http') else 'http://' + str(url)
                             for url in upload_only_urls if url]
        # disable SSL certificate warnings:
        urllib3.disable_warnings()
        self._auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)
        self._proxies = {"http": None, "https": None}
        self._session = requests.Session()

    def __del__(self):
        self._session.close()

    @property
    def public_url(self) -> str or None:
        """
        :return: Public url to conduit
        """
        if not self._download_urls:
            return None
        return self._download_urls[0]

    def add_record(self,
                   collection: str,
                   record: Dict[str, Union[str, FileValue, ReferenceValue, Dict]]) \
            -> Dict[str, Union[str, int, float, bool, FileValue, ReferenceValue, Dict]]:
        """
        Create a record in Wasp.

        :param collection: collection name.
        :param record: a dictionary tag -> value, where tag is s String and value can be a String, a FileValue,
            list or dictionary.
        :return: newly created record as a dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.
        """

        return self._as_record(self._upload(['tools', collection, 'records'], tags=Wasp._strip(record.copy())))

    def update_mutable_record(self, collection: str, record_id: str,
                              update_spec: Dict[str, Union[str, FileValue, ReferenceValue, Dict]],
                              remove_tags: Sequence[str] = ()) \
            -> Dict[str, Union[str,  int, float, bool, FileValue, ReferenceValue, Dict]]:
        """
        Update mutable record.

        :param collection: collection name.
        :param record_id: specific record id to update.
        :param update_spec: dictionary-> tags to update or create,
        :param remove_tags: list -> tags names to remove.
        :return: updated record as a dictionary tag -> value,
                where tag is s String and value can be a String or a FileValue.
        """
        return self._as_record(self._update_mutable(['tools', collection, 'records', record_id, 'update'],
                                                    spec=Wasp._strip(update_spec.copy()), remove=remove_tags))

    def set_immutable(self, collection: str, record_id: str) \
            -> Dict[str, Union[str, FileValue, ReferenceValue, Dict]]:
        """
        Set mutable record to be Immutable.

        :param collection: collection name.
        :param record_id: specific record id to update.
        """
        records = self.find_records(collection=collection, record_spec=record_id, latest=True)
        if len(records) == 0:
            raise Exception('Error: record ' + str(record_id) + ' not found')
        if not self._record_is_mutable(record_tags=records[0]):
            return records[0]
        path = ['tools', collection, 'records', record_id, 'set_immutable']
        return self._as_record(self._update_mutable(path=path, spec=dict(), remove=dict()))

    def set_mutable(self, collection: str, record_id: str) \
            -> Dict[str, Union[str, FileValue, ReferenceValue, Dict]]:
        """
                Set immmutable record to be mutable.
                :param collection: collection name.
                :param record_id: specific record id to update. """
        records = self.find_records(collection=collection, record_spec=record_id, latest=True)
        if len(records) == 0:
            raise Exception('Error: record ' + str(record_id) + ' not found')
        path = ['tools', collection, 'records', record_id, 'set_mutable']
        return self._as_record(self._update_mutable(path=path, spec=dict(), remove=dict()))

    def is_mutable(self, collection, record_id: str) -> bool:
        """
                Check if a record is mutable.
                :param collection: collection name.
                :param record_id: string _id """
        records = self.find_records(collection=collection, record_spec=record_id, latest=True)
        if len(records) == 0:
            raise Exception('Error: Could not find record with ID ' + str(record_id))

        return self._record_is_mutable(record_tags=records[0])

    @staticmethod
    def _record_is_mutable(record_tags: dict) -> bool:
        return record_tags.get('conduit_mutable', True)

    def find_records(self, collection: str,
                     record_spec: Optional[Union[str, Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]] = None,
                     latest: bool = True) -> List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]:
        """
        Finds all the records that follow the spec. Spec is defined as a common part of records to find.
        :param collection: collection name.
        :param record_spec: (optional) string _id or dictionary tag -> value, default: None.
            that defines tag values of the requested records.
            If value is a list, then returned entries will contain all possibilities where any of the values is present.
        :param latest: (optional) whether to select all or only latest records (defined by collection). default: True.
        :return: list of records in a format dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.
        """
        path = ['tools', collection, 'records']
        if record_spec and not isinstance(record_spec, dict):
            path.append(str(record_spec))
            # by _id is always latest.
            return [self._as_record(self._get(path, params=None))]
        if latest:
            path.append('latest')
        return self._as_record(self._get(path=path, params=record_spec))

    def delete_record(self, collection: str, record_id: str) -> bool:
        """
        Delete the record with given record_id.

        :param collection: collection name.
        :param record_id: specific record id to delete.
        :return: True is deleted successfully, False otherwise.
        """
        # restAPI which allows only admin instance permission to delete records
        path = ['utils', 'safeDeleteRecords']
        unique_name = collection + record_id
        json = {'tool': collection, 'query': {'unique_name': unique_name}}
        if len(self._download_urls) == 0:
            # This can happen if only upload urls are provided.
            logging.critical('No download server url provided.')
            return False
        exception = ValueError('No value found')
        for _ in range(Wasp._RETRY_ATTEMPTS):
            for server_url in self._download_urls:
                try:
                    url = self._url_join(url=server_url, paths=path)
                    response = self._session.post(url, auth=self._auth, verify=False, proxies=self._proxies, json=json)
                    if response.status_code not in [200, 201]:  # HTTP_SUCCESS
                        exception = ConnectionRefusedError(response.text)
                        continue
                    return True
                except Exception as e:
                    exception = e
                    continue
        raise exception

    @staticmethod
    def get_record_id(record: Dict[str, Union[str, FileValue, ReferenceValue, Dict]]) -> str or None:
        """
        Returns a record id
        :param record: record dictionary
        :return: str
        """
        if record is None:
            return None
        return record.get("_id", None)

    def set_record_metadata(self,
                            collection: str,
                            record_id: str,
                            meta_part) -> Dict[str, Union[str, FileValue, ReferenceValue, Dict]]:
        """
        Some records may have metadata. Metadata can be modified without changing a record.
        Metadata is very resource hungry for Wasp. Try using a minimum required number of meta tags.
        :param collection: collection name as a String.
        :param record_id: record "_id" tag value or unique_name tag value.
        :param meta_part: is a partial record where all keys are meta keys.
            Same format as record. If key is not a meta key - function will fail.
            If key does not exist, it will create a new meta key.
        :return: record
        """
        return self._as_record(self._put(['tools', collection, 'records', record_id, 'meta'], tags=meta_part))

    def get_record_history(self,
                           collection: str,
                           record_id: str) -> List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]:
        """
        Get complete history of the specified record.
        :param collection: collection name as a String.
        :param record_id: record "_id" tag value or unique_name tag value.
        :return: list of records in a format dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.
        """
        return self._as_record(self._get(['tools', collection, 'records', record_id, 'history']))

    def open(self, file_id: str) -> BinaryIO:
        """
        Opens a io.Stream by mongo id. Must be closed.
        :param file_id: Wasp file file_id tag value.
        :return: io.BytesIO
        """
        response = self._get(['file', file_id])
        # TODO: Possibly bad implementation.
        stream = io.BytesIO(response.content)
        stream.name = response.headers['content-disposition'].split('filename=')[1]
        return stream

    def download(self, file_id: str, dir_path: str, file_name: str = None) -> str:
        """
        Download a file by mongo id without opening a stream. Use for big files.
        :param file_id: Wasp file file_id tag value.
        :param dir_path: writable destination directory
        :param file_name: optional file name. If not given will create with original file name.
        :return: file path.
        """
        try:
            if not os.access(dir_path, os.W_OK):
                raise (Exception('Wasp API does not have write permission to ' + dir_path))
            # Need to set this url but it's not pushed yet
            # res = self._get('tools', collection, 'records', record_id, 'files', file_tag)
            response = self._get(['file', file_id], streaming=True)
            if file_name is None:
                file_name = response.headers['content-disposition'].split('filename=')[1]
            file_path = os.path.join(dir_path, file_name)
            # TODO: Possibly Bad implementation, but it is a taken from requests official documentation..
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            # TODO: Check if required to close response stream, because it may be left open.
            raise Exception('Error: Failed to download a file - ' + str(e))
        return file_path

    def get_system_info(self, collection: str) -> SystemInfo:
        """
        Get information about collection (required tags, key tags, types, ...)
        :param collection: Wasp collection name as a String.
        :return: System info class, which gives services about it
        """
        return SystemInfo(
            system_info_record=self._as_record(self._get(path=['system', 'tools', collection, 'tags_object'])))

    def get_tag_values(self,
                       collection: str,
                       tag: str) -> List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]:
        """
        Get possible values for the specified tag (attribute) from the existing records.
        Very long function that can be used for autocomplete. Do not call more than once.
        :param collection: Wasp collection name as a String.
        :param tag: name of the record tag
        :return: list of values already used in collection
        """
        return self._as_record(self._get(['tools', collection, 'tags', tag, 'values']))

    def get_view_info(self, collection: str, view_name: str = "default") -> ViewConfig:
        """
        Get information about how to display documents in a collection. (columns, sorting order, ...)
        :param collection: Wasp collection name as a String.
        :param view_name: view name (default: "default")
        :return: ViewConfig object
        """
        return ViewConfig(
            view_config_record=self._as_record(self._get(['system', 'view_config', collection, view_name])))

    def run_action(self, action: str, params=None):
        """
        Trigger a registered action on the server.
        The server should have a record in "services" collection with name=<action> cmd=... and args=[...]

        :param action: action name. The action should be registered with the WASP/Conduit server.
        :param params: (optional) dictionary with action arguments.
            Pass {stderr: True, stdout: True} to get stdout/stderr collection into DB files.
        :return: action result json. An error is raised if the action terminated with non-zero status.

        :example:
            >>> c = Wasp("...")
            >>> c.run_action("myaction", params={"MY_PARAM1": "1", "MY_PARAM2": "2"})
        """
        params = params or {}
        # Add these to obtain stdout/stderr from the command:
        # 'stdout': True,
        # 'stderr': True
        resp = self._requests_call(
            path=["actions", "services", action],
            tags=params,
            requests_function=self._session.post,
            retry=False
        )
        if resp.status_code != 200:
            # TODO: need to propagate error from the response
            raise Exception("Running action failed")

        return self._json_to_record(resp.json())

    def _get(self, path: List[str], tags=None, params=None, streaming: bool = False):
        if len(self._download_urls) == 0:
            # This can happen if only upload urls are provided.
            logging.critical('No download server url provided.')
            return None
        exception = ValueError('No value found')
        for _ in range(Wasp._RETRY_ATTEMPTS):
            for server_url in self._download_urls:
                try:
                    url = self._url_join(url=server_url, paths=path, params=params)
                    response = self._session.get(url, auth=self._auth, verify=False, json=tags, proxies=self._proxies,
                                                 stream=streaming)
                    if response.status_code not in [200, 201]:
                        exception = ConnectionRefusedError(response.text)
                        continue
                    return response
                except Exception as e:
                    exception = e
                    continue
            time.sleep(Wasp._RETRY_DELAY)
        raise exception

    def _upload(self, path, tags=None):
        try:
            return self._requests_multipart_call(path=path, tags=tags, requests_function=self._session.post)
        except RuntimeError:
            pass
        return self._requests_call(path=path, tags=tags, requests_function=self._session.post)

    def _put(self, path, tags=None):
        try:
            return self._requests_multipart_call(path=path, tags=tags, requests_function=self._session.put)
        except RuntimeError:
            pass
        return self._requests_call(path=path, tags=tags, requests_function=self._session.put)

    def _requests_call(self, path: Sequence[str], tags: dict, requests_function, retry=True):
        """
        Invokes requests_function with server URL and specified relative path
        NOTE: for post/put requests this function ALWAYS uses form/multi-part format (not application/json).

        :param path: relative path as sequence of strings. Example: ["tools", collection, "records"]
        :param tags:
        :param requests_function:
        :param retry: if True, perform several attampts until successful

        :return: HTTP response object. An exception is raised if request is unsuccessful.
        """
        # Remove code duplication
        if len(self._upload_urls) == 0:
            # If any url provided, this will not happen.
            logging.critical('No server url provided.')
            return None
        exception = ValueError('Cannot upload a value.')

        attempts = Wasp._RETRY_ATTEMPTS if retry else 1

        for _ in range(attempts):
            for server_url in self._upload_urls:
                try:
                    url = Wasp._url_join(url=server_url, paths=path)
                    data = {}
                    all_files = {}
                    if tags:
                        Wasp._json_to_data(tags, data, all_files)
                    if not all_files:
                        # Empty file tag is ignored, but it will not work without.
                        all_files = {'': io.StringIO()}
                    response = requests_function(url, auth=self._auth, verify=False, data=data, files=all_files,
                                                 proxies=self._proxies)
                    if response.status_code not in [200, 201]:  # HTTP_CREATED
                        # TODO: Handle status_code to raise correct error.
                        exception = ConnectionRefusedError(response.text)
                        continue
                    return response
                except Exception as e:
                    exception = e
                    continue
            time.sleep(Wasp._RETRY_DELAY)
        raise exception

    def _requests_multipart_call(self, path, tags, requests_function):
        """
        Variation of _requests_call with "tags" being sent using
        explicit JSON-to-string encoding for preserving value types.

        :param path: list of path components
        :param tags: dict of tags
        :param requests_function: self._session.post or self._session.put
        :return: HTTP response object
        """
        # Remove code duplication
        if len(self._upload_urls) == 0:
            # If any url provided, this will not happen.
            logging.critical('No server url provided.')
            return None
        exception = ValueError('Cannot upload a value.')
        for _ in range(Wasp._RETRY_ATTEMPTS):
            for server_url in self._upload_urls:
                try:
                    url = Wasp._url_join(url=server_url, paths=path)
                    json_tags, files = Wasp._json_to_multipart(tags=tags)
                    multipart = {'conduit_json': (None, dumps(json_tags), 'application/json')}
                    for file_key, file_stream in files.items():
                        multipart[file_key] = (os.path.basename(file_stream.name), file_stream,
                                               'application/octet-stream')
                    response = requests_function(url, auth=self._auth, verify=False, files=multipart,
                                                 proxies=self._proxies)
                    if response.status_code not in [200, 201]:  # HTTP_CREATED
                        if response.status_code == 404:
                            raise RuntimeError(response.text)
                        # TODO: Handle status_code to raise correct error.
                        exception = ConnectionRefusedError(response.text)
                        continue
                    return response
                except RuntimeError as e:
                    raise e
                except Exception as e:
                    exception = e
                    continue
            time.sleep(Wasp._RETRY_DELAY)
        raise exception

    def _update_mutable(self, path, spec: dict, remove: Sequence[str]):
        """
        Update mutable record adding/modifying values in SPEC and removing value in REMOVE
        """
        if len(self._upload_urls) == 0:
            # If any url provided, this will not happen.
            logging.critical('No server url provided.')
            return None

        exception = ValueError('Cannot upload a value.')
        for _ in range(Wasp._RETRY_ATTEMPTS):
            for server_url in self._upload_urls:
                try:
                    url = Wasp._url_join(url=server_url, paths=path)
                    json_tags, files = Wasp._json_to_multipart(tags=spec)
                    multipart = {'conduit_update': (None, dumps(json_tags), 'application/json')}
                    for file_key, file_stream in files.items():
                        multipart[file_key] = (os.path.basename(file_stream.name), file_stream,
                                               'application/octet-stream')
                    multipart['conduit_remove'] = (None, dumps(remove), 'application/json')
                    response = self._session.put(url, auth=self._auth, verify=False, files=multipart,
                                                 proxies=self._proxies)
                    if response.status_code not in [200, 201]:  # HTTP_CREATED
                        if response.status_code == 404:
                            raise RuntimeError(response.text)
                        # TODO: Handle status_code to raise correct error.
                        exception = ConnectionRefusedError(response.text)
                        continue
                    return response
                except RuntimeError as e:
                    raise e
                except Exception as e:
                    exception = e
                    continue
            time.sleep(Wasp._RETRY_DELAY)
        raise exception

    @staticmethod
    def _json_to_multipart(tags: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, FileValue]]:
        """
        Replace files with file placeholders and record reference value
        :param tags: INPUT file - dictionary
        :return: None
        """
        result = {}
        files = {}
        for k, v in tags.items():
            if isinstance(v, dict):
                result[k], f = Wasp._json_to_multipart(v)
                files.update(f)
                continue
            if isinstance(v, FileValue):
                v.seek(0)
                name = str(id(v))
                files[name] = v
                result[k] = {"type": "conduit_file", "name": name}
                continue
            if isinstance(v, ReferenceValue):
                # need to extract json entry for json content:
                result[k] = v.get_entry()
                continue
            result[k] = v
        return result, files

    def _as_record(self, response):
        """
        Wrapper to recursive _json_to_record.
        :param response: requests response
        :return: Wasp record
        """
        if response is None:
            return None
        return self._json_to_record(response.json())

    def _json_to_record(self, json_dict):
        """
        Recursive function that converts a dictionary to an entry.
        :param json_dict: json formatted dictionary.
        :return: entry
        """
        if json_dict is None:
            return None
        if isinstance(json_dict, list):
            new_json = []
            for j in json_dict:
                new_json.append(self._json_to_record(j))
            return new_json
        if isinstance(json_dict, dict):
            if 'type' in json_dict.keys():
                if json_dict['type'] == 'mongo_file':
                    return FileValue(value=json_dict['mongo_id'], name=json_dict['name'], conduit=self)
                if json_dict['type'] == 'mongo_reference':
                    return ReferenceValue(value=json_dict['mongo_id'],
                                          collection=json_dict['mongo_collection'],
                                          conduit=self)
                # Do not change records of some 'type' which are not a mongo_file.
                # They may be special cases that may require API extensions.
                # return json_dict
            new_json = {}
            for key in json_dict.keys():
                new_json[key] = self._json_to_record(json_dict[key])
            return new_json
        return json_dict

    @staticmethod
    def _url_join(url, paths: Sequence[str], params=None):
        """
        Join parts of URL with parameters
        :param url: base url (possibly with parameters) +
        :param paths: additional paths
        :param params: additional parameters
        :return: new URL string
        """
        parsed_url = urlparse(url)
        if len(paths):
            # append paths to base url path
            base_path = str(parsed_url.path).split('/') if parsed_url.path != '/' else ['']
            parsed_path = '/'.join(base_path + list(paths))
        else:
            parsed_path = parsed_url.path

        if params is not None:
            parsed_query = parse_qsl(parsed_url.query, keep_blank_values=True)
            out_dict = {}
            Wasp._flatten(tags=params, data=out_dict)
            parsed_query.extend(out_dict.items())
            parsed_query = urlencode(parsed_query)
        else:
            parsed_query = parsed_url.query
        parsed_url = urlunparse((parsed_url[0], parsed_url[1], parsed_path, parsed_url[3], parsed_query, parsed_url[5]))
        return parsed_url

    @staticmethod
    def _flatten(tags, data, prefix=''):
        """
        Convert hierarchical dictionary to a flat dict with indexed names in post data format
        :param tags: INPUT file - dictionary
        :param data: OUTPUT dict must be defined
        :param prefix: recursion parameter
        :return: None
        """
        for k, v in tags.items():
            if isinstance(v, dict):
                sub_key = k + '.' if prefix == '' else prefix + k + '.'
                Wasp._flatten(tags=v, data=data, prefix=sub_key)
                continue
            sub_key = k if prefix == '' else prefix + k
            if isinstance(v, list):
                data[sub_key] = ','.join(v)
                continue
            data[sub_key] = v

    @staticmethod
    def _json_to_data(tags, data, files, prefix=''):
        """
        Convert hierarchical dictionary to a flat dict with indexed names in post data format
        :param tags: INPUT file - dictionary
        :param data: OUTPUT file must be defined
        :param files: OUTPUT file must be defined
        :param prefix: recursion parameter
        :return: None
        """
        for k, v in tags.items():
            sub_key = k + '[' if prefix == '' else prefix + k + ']['
            if isinstance(v, dict):
                Wasp._json_to_data(v, data, files, prefix=sub_key)
                continue
            if isinstance(v, ReferenceValue):
                Wasp._json_to_data(v.get_entry(), data, files, prefix=sub_key)
                continue
            sub_key = k if prefix == '' else prefix + k + ']'
            if isinstance(v, FileValue):
                v.seek(0)
                files[sub_key] = v
                continue
            data[sub_key] = v

    @staticmethod
    def _strip(record):
        record.pop('date', None)
        record.pop('_id', None)
        record.pop('conduitVersion', None)
        record.pop('unique_name', None)
        record.pop('version', None)
        try:
            for k, v in record.items():
                Wasp._strip(v)
        except AttributeError:
            pass
        return record
