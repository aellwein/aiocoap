from itertools import chain

from .numbers import *

def readExtendedFieldValue(value, rawdata):
    """Used to decode large values of option delta and option length
       from raw binary form."""
    if value >= 0 and value < 13:
        return (value, rawdata)
    elif value == 13:
        return (rawdata[0] + 13, rawdata[1:])
    elif value == 14:
        return (struct.unpack('!H', rawdata[:2])[0] + 269, rawdata[2:])
    else:
        raise ValueError("Value out of range.")


def writeExtendedFieldValue(value):
    """Used to encode large values of option delta and option length
       into raw binary form.
       In CoAP option delta and length can be represented by a variable
       number of bytes depending on the value."""
    if value >= 0 and value < 13:
        return (value, b'')
    elif value >= 13 and value < 269:
        return (13, struct.pack('!B', value - 13))
    elif value >= 269 and value < 65804:
        return (14, struct.pack('!H', value - 269))
    else:
        raise ValueError("Value out of range.")


def _single_value_view(option_number):
    """Generate a property for a given option number, where the option is not
    repeatable. For getting, it will return the value of the first option
    object with matching number. For setting, it will remove all options with
    that number and create one with the given value. The property can be
    deleted, resulting in removal of the option from the header.

    For consistency, setting the value to None also clears the option. (Note
    that with the currently implemented optiontypes, None is not a valid value
    for any of them)."""

    def _getter(self, option_number=option_number):
        options = self.getOption(option_number)
        if not options:
            return None
        else:
            return options[0].value

    def _setter(self, value, option_number=option_number):
        self.deleteOption(option_number)
        if value is not None:
            self.addOption(option_number.create_option(value=value))

    def _deleter(self, value, option_number=option_number):
        self.deleteOption(option_number)

    return property(_getter, _setter, _deleter, "Single-value view on the %s option."%option_number)

def _items_view(option_number):
    """Generate a property for a given option number, where the option is
    repeatable. For getting, it will return a tuple of the values of the option
    objects with matching number. For setting, it will remove all options with
    that number and create new ones from the given iterable."""

    def _getter(self, option_number=option_number):
        return tuple(o.value for o in self.getOption(option_number))

    def _setter(self, value, option_number=option_number):
        self.deleteOption(option_number)
        for v in value:
            self.addOption(option_number.create_option(value=v))

    def _deleter(self, value, option_number=option_number):
        self.deleteOption(option_number)

    return property(_getter, _setter, doc="Iterable view on the %s option."%option_number)

class Options(object):
    """Represent CoAP Header Options."""
    def __init__(self):
        self._options = {}

    def decode(self, rawdata):
        """Decode all options in message from raw binary data."""
        option_number = OptionNumber(0)

        while len(rawdata) > 0:
            if rawdata[0] == 0xFF:
                return rawdata[1:]
            dllen = rawdata[0]
            delta = (dllen & 0xF0) >> 4
            length = (dllen & 0x0F)
            rawdata = rawdata[1:]
            (delta, rawdata) = readExtendedFieldValue(delta, rawdata)
            (length, rawdata) = readExtendedFieldValue(length, rawdata)
            option_number += delta
            option = option_number.create_option(decode=rawdata[:length])
            self.addOption(option)
            rawdata = rawdata[length:]
        return ''

    def encode(self):
        """Encode all options in option header into string of bytes."""
        data = []
        current_opt_num = 0
        option_list = self.optionList()
        for option in option_list:
            delta, extended_delta = writeExtendedFieldValue(option.number - current_opt_num)
            length, extended_length = writeExtendedFieldValue(option.length)
            data.append(bytes([((delta & 0x0F) << 4) + (length & 0x0F)]))
            data.append(extended_delta)
            data.append(extended_length)
            data.append(option.encode())
            current_opt_num = option.number
        return (b''.join(data))

    def addOption(self, option):
        """Add option into option header."""
        self._options.setdefault(option.number, []).append(option)

    def deleteOption(self, number):
        """Delete option from option header."""
        if number in self._options:
            self._options.pop(number)

    def getOption(self, number):
        """Get option with specified number."""
        return self._options.get(number, ())

    def optionList(self):
        return chain.from_iterable(sorted(self._options.values(), key=lambda x: x[0].number))

    uri_path = _items_view(OptionNumber.URI_PATH)
    uri_query = _items_view(OptionNumber.URI_QUERY)
    block2 = _single_value_view(OptionNumber.BLOCK2)
    block1 = _single_value_view(OptionNumber.BLOCK1)
    content_format = _single_value_view(OptionNumber.CONTENT_FORMAT)
    etag = _single_value_view(OptionNumber.ETAG) # used in responses
    etags = _items_view(OptionNumber.ETAG) # used in requests
    observe = _single_value_view(OptionNumber.OBSERVE)
    accept = _single_value_view(OptionNumber.ACCEPT)
    uri_host = _single_value_view(OptionNumber.URI_HOST)
    uri_port = _single_value_view(OptionNumber.URI_PORT)
