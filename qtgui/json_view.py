from typing import Dict, Union, Any, Tuple, Optional

from PyQt5 import Qt

STYLE = "<style>" \
        ".key, a {" \
        "  color: \"green\";" \
        "  text-decoration: none;" \
        "}" \
        ".value {" \
        "  color: \"darkred\";" \
        "}" \
        "</style>\n"


class JsonView(Qt.QLabel):
    """
    Shows a JSON object
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._expand = set()
        self._id2path = {}
        self._path2id = {}
        self._json = None

        self.setBackgroundRole(Qt.QPalette.Base)
        self.setAlignment(Qt.Qt.AlignTop | Qt.Qt.AlignLeft)
        self.setTextFormat(Qt.Qt.RichText)
        self.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse | Qt.Qt.LinksAccessibleByMouse)
        self.linkActivated.connect(self._on_expand)

    def set_json(self, record: Optional[Dict]) -> None:
        """
        Set JSON record to update on view
        :param record: JSON record
        :return:
        """
        self._expand = set()
        self._id2path = {}
        self._path2id = {}
        self._json = record
        self._update()

    def _update(self) -> None:
        # Update displayed HTML
        record = self._json
        if record is None:
            self.setText("")
        else:
            self.setText(self._print(record))

    def _print(self, record: Dict) -> str:
        """
        Pretty-print JSON into HTML with colors
        :param record: JSON record
        :return: HTML string
        """
        return STYLE + '<pre>{\n' + self._print_content(record, "    ", tuple()) + '\n}</pre>'

    def _print_content(self, record: Dict, pref: str = "", path: Tuple = tuple()) -> str:
        """
        FIXME: typing
        Print record content with prefix
        :param record: JSON record
        :param pref:
        :param path:
        :return:
        """
        result = []

        if isinstance(record, dict):
            keys = sorted(record.keys())
        else:
            keys = range(len(record))

        for key in keys:
            val = record[key]
            if isinstance(val, dict) or isinstance(val, list):
                open_char, close_char = ('{', '}') if isinstance(val, dict) else ('[', ']')
                anchor = self._print_anchor(path + (key,), JsonView._print_key(key))
                if (path + (key,)) in self._expand:
                    result.append(pref + '<span class="key">' + anchor + '</span>: ' + open_char)
                    result.append(self._print_content(val, "    " + pref, path + (key,)))
                    result.append(pref + close_char)
                else:
                    result.append(pref + '<span class="key">' + anchor + '</span>: {...}')
            else:
                result.append(pref + '<span class="key">"' + str(key) + '"</span>: ' + JsonView._print_value(val))

        return ',\n'.join(result)

    @staticmethod
    def _print_key(val: Union[str, int]) -> str:
        """
        Print key (string or integer)
        :param val: value to print
        :return: HTML string
        """
        if isinstance(val, int):
            return str(int)
        else:
            return '"' + val + '"'

    @staticmethod
    def _print_value(val: Any) -> str:
        """
        Print simple values (int, bool, string)
        :param val: value to print
        :return: HTML string
        """
        if isinstance(val, str):
            val = '"' + val + '"'
        else:
            val = str(val)
        return '<span class="value">' + val + '</span>'

    def _print_anchor(self, path, val) -> str:
        """
        FIXME: typing
        Generate an anchor string to expand/collapse
        :param path:
        :param val:
        :return: HTML string
        """
        # generate new id for the link or reuse existing:
        if path in self._path2id:
            a_id = self._path2id[path]
        else:
            a_id = len(self._path2id)
            self._path2id[path] = a_id
            self._id2path[a_id] = path

        return '<a href=' + str(a_id) + '>' + val + '</a>'

    def _on_expand(self, link_id: str) -> None:
        """
        Called when user clicks to expand / collapse a sub-document
        :param link_id: link ID
        :return:
        """
        link_id = int(link_id)
        path = self._id2path[link_id]
        if path in self._expand:
            self._expand.remove(path)
        else:
            self._expand.add(path)

        self._update()
