Module py_wasp
==============

Classes
-------

`FileValue(value, name=None, conduit=None)`
:   Buffered I/O implementation using an in-memory bytes buffer.
    
    Wasp record file value, used for uploading and downloading files in records.
    e.g. Record can be a dictionary in a format: { "tag_for_file": FileValue(args) }
    Interface equivalent to return value of open(file, "r", encoding="utf-8")
    Additional function "to_file" saves the file to a disk in a more memory efficient way.
    Additional property "file_id" returns a file id if FileValue is already stored in Wasp, None otherwise.
    :param value: io.Stream, path to a file, mongo id or a string that needs to be written as a file.
    :param name: optional name override for a file.
    :param conduit: Wasp to use if value is a mongo id.

    ### Ancestors (in MRO)

    * _io.BytesIO
    * _io._BufferedIOBase
    * _io._IOBase

    ### Instance variables

    `file_id: Optional[str]`
    :   :return: mongo id if stored in Wasp, None otherwise.

    `file_url: Optional[str]`
    :   :return: Wasp download path if stored in Wasp, None otherwise.

    `name: str`
    :   :return: Stream name.

    ### Methods

    `to_file(self, dir_path) ‑> str`
    :   Writes a file to dir_path directory in a more memory efficient way. Use for big files.
        :param dir_path: directory where to store a file.
        :return: path to a created file.

`ReferenceValue(value: Union[str, Dict[~KT, ~VT]], collection: str, conduit: Wasp = None)`
:   :param value: mongo id or the whole conduit record.
    :param collection:
    :param conduit:

    ### Methods

    `get_entry(self)`
    :

    `get_record(self)`
    :

`SystemInfo(system_info_record)`
:   Wasp collection system info.
    :param system_info_record: Wasp system_info_record as a dictionary String -> String.

    ### Instance variables

    `key_tags: List[str]`
    :   Get key tags of a collection.
        :return: mandatory tags array

    `mandatory_tags: List[str]`
    :   Get mandatory tags of a collection.
        :return: mandatory tags array

    `tags: List[str]`
    :   :return: list of all defined tags names for the collection.

    ### Methods

    `get_default_value(self, tag) ‑> str`
    :   :param tag: tag name (string).
        :return: tag default value (string).

    `get_possible_values(self, tag) ‑> List[str]`
    :   :param tag: tag name (string).
        :return: list of possible values for the specified tag.

`ViewConfig(view_config_record)`
:   Wasp collection view configuration.

    ### Class variables

    `Column`
    :

    ### Instance variables

    `columns: List[py_wasp.Column]`
    :   :return: list of Column objects describing the columns to display.

`Wasp(server_urls: Union[str, List[str], None] = None, upload_only_urls: Optional[List[str]] = None)`
:   Interface for WASP.
    Wasp Record is defined as a dictionary: tag -> value,
        where tag is a String and value can be a String, boolean, int, float or a FileValue.
    Keys and values in other formats are converted to Strings when possible.
    
    :param server_urls: server urls with ports as a list or a as a single value.
    :param upload_only_urls: server urls for uploads in case they are different from downloads.

    ### Static methods

    `get_record_id(record: Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]) ‑> str`
    :   Returns a record id
        :param record: record dictionary
        :return: str

    ### Instance variables

    `public_url: str`
    :   :return: Public url to conduit

    ### Methods

    `add_record(self, collection: str, record: Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]) ‑> Dict[str, Union[str, int, float, bool, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]`
    :   Create a record in Wasp.
        
        :param collection: collection name.
        :param record: a dictionary tag -> value, where tag is s String and value can be a String, a FileValue,
            list or dictionary.
        :return: newly created record as a dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.

    `delete_record(self, collection: str, record_id: str) ‑> bool`
    :   Delete the record with given record_id.
        
        :param collection: collection name.
        :param record_id: specific record id to delete.
        :return: True is deleted successfully, False otherwise.

    `download(self, file_id: str, dir_path: str, file_name: str = None) ‑> str`
    :   Download a file by mongo id without opening a stream. Use for big files.
        :param file_id: Wasp file file_id tag value.
        :param dir_path: writable destination directory
        :param file_name: optional file name. If not given will create with original file name.
        :return: file path.

    `find_records(self, collection: str, record_spec: Union[str, Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]], None] = None, latest: bool = True) ‑> List[Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]]`
    :   Finds all the records that follow the spec. Spec is defined as a common part of records to find.
        :param collection: collection name.
        :param record_spec: (optional) string _id or dictionary tag -> value, default: None.
            that defines tag values of the requested records.
            If value is a list, then returned entries will contain all possibilities where any of the values is present.
        :param latest: (optional) whether to select all or only latest records (defined by collection). default: True.
        :return: list of records in a format dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.

    `get_record_history(self, collection: str, record_id: str) ‑> List[Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]]`
    :   Get complete history of the specified record.
        :param collection: collection name as a String.
        :param record_id: record "_id" tag value or unique_name tag value.
        :return: list of records in a format dictionary tag -> value,
            where tag is s String and value can be a String or a FileValue.

    `get_system_info(self, collection: str) ‑> py_wasp.SystemInfo`
    :   Get information about collection (required tags, key tags, types, ...)
        :param collection: Wasp collection name as a String.
        :return: System info class, which gives services about it

    `get_tag_values(self, collection: str, tag: str) ‑> List[Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]]`
    :   Get possible values for the specified tag (attribute) from the existing records.
        Very long function that can be used for autocomplete. Do not call more than once.
        :param collection: Wasp collection name as a String.
        :param tag: name of the record tag
        :return: list of values already used in collection

    `get_view_info(self, collection: str, view_name: str = 'default') ‑> py_wasp.ViewConfig`
    :   Get information about how to display documents in a collection. (columns, sorting order, ...)
        :param collection: Wasp collection name as a String.
        :param view_name: view name (default: "default")
        :return: ViewConfig object

    `is_mutable(self, collection, record_id: str) ‑> bool`
    :   Check if a record is mutable.
        :param collection: collection name.
        :param record_id: string _id

    `open(self, file_id: str) ‑> <class 'BinaryIO'>`
    :   Opens a io.Stream by mongo id. Must be closed.
        :param file_id: Wasp file file_id tag value.
        :return: io.BytesIO

    `run_action(self, action: str, params=None)`
    :   Trigger a registered action on the server.
        The server should have a record in "services" collection with name=<action> cmd=... and args=[...]
        
        :param action: action name. The action should be registered with the WASP/Conduit server.
        :param params: (optional) dictionary with action arguments.
            Pass {stderr: True, stdout: True} to get stdout/stderr collection into DB files.
        :return: action result json. An error is raised if the action terminated with non-zero status.
        
        :example:
            >>> c = Wasp("...")
            >>> c.run_action("myaction", params={"MY_PARAM1": "1", "MY_PARAM2": "2"})

    `set_immutable(self, collection: str, record_id: str) ‑> Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]`
    :   Set mutable record to be Immutable.
        
        :param collection: collection name.
        :param record_id: specific record id to update.

    `set_mutable(self, collection: str, record_id: str) ‑> Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]`
    :   Set immmutable record to be mutable.
        :param collection: collection name.
        :param record_id: specific record id to update.

    `set_record_metadata(self, collection: str, record_id: str, meta_part) ‑> Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]`
    :   Some records may have metadata. Metadata can be modified without changing a record.
        Metadata is very resource hungry for Wasp. Try using a minimum required number of meta tags.
        :param collection: collection name as a String.
        :param record_id: record "_id" tag value or unique_name tag value.
        :param meta_part: is a partial record where all keys are meta keys.
            Same format as record. If key is not a meta key - function will fail.
            If key does not exist, it will create a new meta key.
        :return: record

    `update_mutable_record(self, collection: str, record_id: str, update_spec: Dict[str, Union[str, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]], remove_tags: Sequence[str] = ()) ‑> Dict[str, Union[str, int, float, bool, py_wasp.FileValue, py_wasp.ReferenceValue, Dict[~KT, ~VT]]]`
    :   Update mutable record.
        
        :param collection: collection name.
        :param record_id: specific record id to update.
        :param update_spec: dictionary-> tags to update or create,
        :param remove_tags: list -> tags names to remove.
        :return: updated record as a dictionary tag -> value,
                where tag is s String and value can be a String or a FileValue.