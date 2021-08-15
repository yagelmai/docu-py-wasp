import json
import logging
import os
import unittest
import sys
import getpass

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))  # noqa
from py_wasp import Wasp, FileValue, ReferenceValue  # noqa


class TestPyWasp(unittest.TestCase):
    _UPDATE_EXPECTED = False
    _EXPECTED = '_expected.json'
    _RESULT = '.json'

    def setUp(self):
        self._dir = os.path.realpath(__file__)[:-3] + '_'
        if not os.path.isdir(self._dir):
            os.makedirs(self._dir)
        logging.debug(self._dir)
        test_tuna_server = False
        if test_tuna_server:  # Run on Tuna server
            try:
                logging.critical('Running under user: ' + str(getpass.getuser()))
            except Exception as e:
                logging.critical('Unable to determine user: ' + str(e))
            self.server_url = 'http://iapp405.iil.intel.com:2233'
            self._test_collection = 'test'
            self._mutable_support = False
        else:  # Run on Wasp internal testing
            self.server_url = 'https://wasp-testing.malina.intel.com'
            self._test_collection = 'test_PyWasp'
            self._mutable_support = True
        self.api = Wasp(server_urls=[self.server_url])
        self._update_expected = TestPyWasp._UPDATE_EXPECTED

    def test_find_records(self):
        name = 'test_find_records'
        ret = []
        record_spec = {"Comment": "Welcome to Tuna"}
        for record in self.api.find_records(collection='tuna_studies', record_spec=record_spec):
            ret.append(TestPyWasp._strip(record))
        logging.debug(ret)
        self._handle_result(name, {'records': ret})

    def test_find_records_with_files(self):
        name = 'test_find_records_with_files'
        # Must exist from previous runs.
        record = {
            'study': 'test_add_record_with_files',
            'work_area': 'wa',
        }
        ret = self.api.find_records(collection=self._test_collection, record_spec=record, latest=True)
        conf_file = ret[0].get('configuration', None)
        self.assertIsNotNone(conf_file)
        self._handle_result(name, json.load(conf_file))

    def test_add_record(self):
        name = 'test_add_record'
        record = {
            'study': name,
            'work_area': 'wa',
            'runner': 'test_runner',
            'algorithm': 'test_algorithm',
            'reader': 'test_reader',
            'group': {'a': 'b'}
        }
        ret = TestPyWasp._strip(self.api.add_record(collection=self._test_collection, record=record))
        logging.debug(ret)
        self._handle_result(name, {'records': ret})

    def test_add_record_with_files(self):
        name = 'test_add_record_with_files'
        record = {
            'study': name,
            'work_area': 'wa',
            'configuration': FileValue(value=os.path.join(self._dir, 'configuration.json')),
            'runner': {'module': 'test_runner'},
            'algorithm': {'module': 'test_algorithm',
                          'configuration': FileValue(value=os.path.join(self._dir, 'algorithm.json'))},
            'reader': {'module': 'test_reader'},
            'cost': {'module': 'test_cost'},
        }
        ret = self.api.add_record(collection=self._test_collection, record=record)
        logging.debug(ret)
        self._handle_result(name, {'records': TestPyWasp._strip(ret)})

    def test_add_record_with_reference(self):
        # This record we want to get back in the end:
        record_to_find_after_adding = {
            'study': 'test_reference',
            'work_area': 'wa',
            'runner': 'test_runner',
            'algorithm': 'test_algorithm',
            'reader': 'test_reader',
            'group': {'a': 'b'}
        }
        # When we added it, we can now create a reference from it:
        reference_record = self.api.add_record(collection=self._test_collection, record=record_to_find_after_adding)

        name = 'test_add_record_with_reference'
        record = {
            'study': name,
            'my_reference': ReferenceValue(value=reference_record, collection=self._test_collection)
        }
        # Add a record:
        added_record = TestPyWasp._strip(self.api.add_record(collection=self._test_collection, record=record))
        print(added_record)
        added_record.pop('my_reference')

        # Get record back:
        found_record = self.api.find_records(collection=self._test_collection,
                                             record_spec=added_record,
                                             latest=True)[0]
        returned_reference = found_record['my_reference']
        ret = TestPyWasp._strip(returned_reference.get_record())
        logging.debug(ret)
        self._handle_result(name, {'records': ret})

    def test_add_meta_data(self):
        if not self._mutable_support:
            raise unittest.SkipTest('Not running add meta on old version.')

        # Add a record with boolean value on meta data :
        record = {
            'study': 'test_meta_data',
            'work_area': 'wa',
            'runner': 'test_runner',
            'meta_data_tag': {
                'type': 'meta_data',
                'value': True
            }
        }
        added_record = self.api.add_record(collection=self._test_collection, record=record)
        record_id = added_record['_id']
        # now update same record and change boolean:
        ret = self.api.set_record_metadata(collection=self._test_collection, record_id=record_id,
                                           meta_part={'meta_data_tag': False})
        ret = TestPyWasp._strip(ret)
        value = ret.get('meta_data_tag', {}).get('value', {})

        # Check that boolean value was preserved:
        self.assertEqual(False, value, 'Expected: False, got ' + str(value))

    def test_add_mutable_record_with_files(self):
        if not self._mutable_support:
            raise unittest.SkipTest('Not running mutable on old version.')

        name = 'test_add_mutable_record_with_files'
        record = {
            'study': name,
            'work_area': 'wa',
            'configuration': FileValue(value=os.path.join(self._dir, 'configuration.json')),
            'runner': {'module': 'test_runner', 'configuration': None},
            'algorithm': {'module': 'test_algorithm',
                          'configuration': FileValue(value=os.path.join(self._dir, 'algorithm.json'))},
            'reader': {'module': 'test_reader', 'configuration': None},
            'cost': {'module': 'test_cost', 'configuration': None},
        }
        ret = self.api.add_record(collection=self._test_collection, record=record)
        logging.debug(ret)
        self._handle_result(name, {'records': TestPyWasp._strip(ret)})

    def test_change_mutable_record(self):
        if not self._mutable_support:
            raise unittest.SkipTest('Not running mutable on old version.')

        name = 'test_change_mutable_record'
        record = {
            'study': name,
            'work_area': 'wa',
            'runner': {'module': 'test_runner'},
            'to_change_str': "before",
            'to_change_num': 123,
            'to_change_bool': False,
            'to_remove_1': 'value1',
            'to_remove_2': {'key1': 'value', 'key2': 123}
        }
        ret0 = self.api.add_record(collection=self._test_collection, record=record)
        logging.debug(ret0)
        record_id = ret0['_id']

        update_spec = {
            'to_change_str': "after",
            'to_change_num': 456,
            'to_change_bool': True,
        }
        remove_tags = ['to_remove_1', 'to_remove_2']
        ret1 = self.api.update_mutable_record(collection=self._test_collection, record_id=record_id,
                                              update_spec=update_spec, remove_tags=remove_tags)
        self._handle_result(name, {'records': TestPyWasp._strip(ret1)})

    def test_record_set_immutable(self):
        if not self._mutable_support:
            raise unittest.SkipTest('Not running mutable on old version.')

        name = 'test_record_set_immutable'
        record = {
            'study': name,
            'work_area': 'wa'
        }
        ret0 = self.api.add_record(collection=self._test_collection, record=record)
        logging.debug(ret0)
        record_id = ret0['_id']
        ret1 = self.api.set_immutable(collection=self._test_collection, record_id=record_id)

        self._handle_result(name, {'records': TestPyWasp._strip(ret1)})

    def test_record_set_mutable(self):
        if not self._mutable_support:
            raise unittest.SkipTest('Not running mutable on old version.')

        name = 'test_record_set_mutable'
        record = {
            'study': name,
            'work_area': 'wa'
        }
        ret0 = self.api.add_record(collection=self._test_collection, record=record)
        logging.debug(ret0)
        record_id = ret0['_id']
        self.api.set_immutable(collection=self._test_collection, record_id=record_id)
        ret1 = self.api.set_mutable(collection=self._test_collection, record_id=record_id)
        self._handle_result(name, {'records': TestPyWasp._strip(ret1)})

    @staticmethod
    def _strip(record):
        record.pop('date', None)
        record.pop('_id', None)
        record.pop('conduitVersion', None)
        record.pop('unique_name', None)
        record.pop('user', None)
        record.pop('mongo_id', None)
        record.pop('version', None)
        record.pop('latestVersion', None)
        record.pop('conduit_mutable_update_date', None)
        record.pop('conduit_immutable_date', None)
        try:
            for k, v in record.items():
                TestPyWasp._strip(v)
        except AttributeError:
            pass
        return record

    def _handle_result(self, name, result):
        result_file = os.path.join(self._dir, name + self._RESULT)
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)
        TestPyWasp._json_dump(result, result_file)

        expected_file = os.path.join(self._dir, name + self._EXPECTED)
        if self._update_expected:
            TestPyWasp._json_dump(result, expected_file)

        with open(result_file, 'r') as f:
            result = json.load(f)
        with open(expected_file, 'r') as f:
            expected = json.load(f)

        self.assertEqual(dict(expected), dict(result), 'Expected ' + str(expected) + ' got ' + str(result))
        os.remove(result_file)

    @staticmethod
    def _json_dump(obj, path):
        """
        Dump only dictionaries, and they can contain numpy.int64.
        This function takes care that all files are stored in same format.
        :param obj: parameters or metrics object
        :param path: full path for destination
        :return: None
        """
        if isinstance(obj, dict):
            obj = dict(obj)
        with open(path, 'w') as f:
            json.dump(obj, f, sort_keys=True, indent=4, default=TestPyWasp._default)

    @staticmethod
    def _default(o):
        """
        Helper function for json dump. Converts numpy.int64 to int
        :param o: numpy.int64
        :return: int
        """
        try:
            # If name is given, it is enough for testing.
            return o.name
        except AttributeError:
            pass
        try:
            # Creates a simple dict:
            return dict(o)
        except (ValueError, OSError):
            pass
        try:
            # Creates a simple list:
            return list(o)
        except (ValueError, OSError):
            pass
        logging.warning('Cannot handle ' + str(o.__class__))
        return str(o)
