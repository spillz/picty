#!/usr/bin/python
# -*- coding: utf-8 -*-

# ******************************************************************************
#
# Copyright (C) 2006-2008 Olivier Tilloy <olivier@tilloy.net>
#
# This file is part of the pyexiv2 distribution.
#
# pyexiv2 is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# pyexiv2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyexiv2; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, 5th Floor, Boston, MA 02110-1301 USA.
#
#
# File:      pyexiv2.py
# Author(s): Olivier Tilloy <olivier@tilloy.net>
#
# ******************************************************************************

"""
Manipulation of EXIF and IPTC metadata embedded in image files.

This module provides a single class, Image, and utility functions to manipulate
EXIF and IPTC metadata embedded in image files such as JPEG and TIFF files.
EXIF and IPTC metadata can be accessed in both read and write modes.

This module is a higher-level interface to the Python binding of the excellent
C++ library Exiv2, libpyexiv2.
Its only class, Image, inherits from libpyexiv2.Image and provides convenient
methods for the manipulation of EXIF and IPTC metadata using Python's built-in
types and modules such as datetime.
These methods should be preferred to the ones directly provided by
libpyexiv2.Image.

A typical use of this binding would be:

>>> import pyexiv2
>>> import datetime
>>> image = pyexiv2.Image('test/smiley.jpg')
>>> image.readMetadata()
>>> print image.exifKeys()
['Exif.Image.ImageDescription', 'Exif.Image.XResolution', 'Exif.Image.YResolution', 'Exif.Image.ResolutionUnit', 'Exif.Image.Software', 'Exif.Image.DateTime', 'Exif.Image.Artist', 'Exif.Image.Copyright', 'Exif.Image.ExifTag', 'Exif.Photo.Flash', 'Exif.Photo.PixelXDimension', 'Exif.Photo.PixelYDimension']
>>> print image['Exif.Image.DateTime']
2004-07-13 21:23:44
>>> image['Exif.Image.DateTime'] = datetime.datetime.today()
>>> image.writeMetadata()

"""

import libpyexiv2

import time
import datetime
import re

class FixedOffset(datetime.tzinfo):

	"""
	Fixed offset from a local time east from UTC.

	Represent a fixed (positive or negative) offset from a local time in hours
	and minutes.

	Public methods:
	utcoffset -- return offset of local time from UTC, in minutes east of UTC
	dst -- return the daylight saving time (DST) adjustment, here always 0
	tzname -- return a string representation of the offset with format '±%H%M'
	"""

	def __init__(self, offsetSign='+', offsetHours=0, offsetMinutes=0):
		"""
		Constructor.

		Construct a FixedOffset object from an offset sign ('+' or '-') and an
		offset absolute value expressed in hours and minutes.
		No check on the validity of those values is performed, it is the
		responsibility of the caller to pass correct values to the constructor.

		Keyword arguments:
		offsetSign -- the sign of the offset ('+' or '-')
		offsetHours -- the absolute number of hours of the offset
		offsetMinutes -- the absolute number of minutes of the offset
		"""
		self.offsetSign = offsetSign
		self.offsetHours = offsetHours
		self.offsetMinutes = offsetMinutes

	def utcoffset(self, dt):
		"""
		Return offset of local time from UTC, in minutes east of UTC.

		Return offset of local time from UTC, in minutes east of UTC.
		If local time is west of UTC, this should be negative.
		The value returned is a datetime.timedelta object specifying a whole
		number of minutes in the range -1439 to 1439 inclusive.

		Keyword arguments:
		dt -- the datetime.time object representing the local time
		"""
		totalOffsetMinutes = self.offsetHours * 60 + self.offsetMinutes
		if self.offsetSign == '-':
			totalOffsetMinutes = -totalOffsetMinutes
		return datetime.timedelta(minutes = totalOffsetMinutes)

	def dst(self, dt):
		"""
		Return the daylight saving time (DST) adjustment.

		Return the daylight saving time (DST) adjustment.
		In this implementation, it is always nil, and the method return
		datetime.timedelta(0).

		Keyword arguments:
		dt -- the datetime.time object representing the local time
		"""
		return datetime.timedelta(0)

	def tzname(self, dt):
		"""
		Return a string representation of the offset.

		Return a string representation of the offset with format '±%H:%M'.

		Keyword arguments:
		dt -- the datetime.time object representing the local time
		"""
		string = self.offsetSign
		string = string + ('%02d' % self.offsetHours) + ':'
		string = string + ('%02d' % self.offsetMinutes)
		return string

def UndefinedToString(undefined):
	"""
	Convert an undefined string into its corresponding sequence of bytes.

	Convert a string containing the ascii codes of a sequence of bytes, each
	followed by a blank space, into the corresponding string (e.g.
	"48 50 50 49 " will be converted into "0221").
	The Undefined type is defined in the EXIF specification.

	Keyword arguments:
	undefined -- the string containing the ascii codes of a sequence of bytes
	"""
	return ''.join(map(lambda x: chr(int(x)), undefined.rstrip().split(' ')))

def StringToUndefined(sequence):
	"""
	Convert a string containing a sequence of bytes into its undefined form.

	Convert a string containing a sequence of bytes into the corresponding
	sequence of ascii codes, each followed by a blank space (e.g. "0221" will
	be converted into "48 50 50 49 ").
	The Undefined type is defined in the EXIF specification.

	Keyword arguments:
	sequence -- the string containing the sequence of bytes
	"""
	return ''.join(map(lambda x: '%d ' % ord(x), sequence))

def StringToDateTime(string):
	"""
	Try to convert a string containing a date and time to a datetime object.

	Try to convert a string containing a date and time to the corresponding
	datetime object. The conversion is done by trying several patterns for
	regular expression matching.
	If no pattern matches, the string is returned unchanged.

	Keyword arguments:
	string -- the string potentially containing a date and time
	"""
	# Possible formats to try
	# According to the EXIF specification [http://www.exif.org/Exif2-2.PDF], the
	# only accepted format for a string field representing a datetime is
	# '%Y-%m-%d %H:%M:%S', but it seems that others formats can be found in the
	# wild, so this list could be extended to include new exotic formats.
	formats = ['%Y-%m-%d %H:%M:%S', '%Y:%m:%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']

	for format in formats:
		try:
			t = time.strptime(string, format)
			return datetime.datetime(*t[:6])
		except ValueError:
			# the tested format does not match, do nothing
			pass

	# none of the tested formats matched, return the original string unchanged
	return string

def StringToDate(string):
	"""
	Try to convert a string containing a date to a date object.

	Try to convert a string containing a date to the corresponding date object.
	The conversion is done by matching a regular expression.
	If the pattern does not match, the string is returned unchanged.

	Keyword arguments:
	string -- the string potentially containing a date
	"""
	# According to the IPTC specification
	# [http://www.iptc.org/std/IIM/4.1/specification/IIMV4.1.pdf], the format
	# for a string field representing a date is '%Y%m%d'.
	# However, the string returned by exiv2 using method DateValue::toString()
	# is formatted using pattern '%Y-%m-%d'.
	format = '%Y-%m-%d'
	try:
		t = time.strptime(string, format)
		return datetime.date(*t[:3])
	except ValueError:
		# the tested format does not match, do nothing
		return string

def StringToTime(string):
	"""
	Try to convert a string containing a time to a time object.

	Try to convert a string containing a time to the corresponding time object.
	The conversion is done by matching a regular expression.
	If the pattern does not match, the string is returned unchanged.

	Keyword arguments:
	string -- the string potentially containing a time
	"""
	# According to the IPTC specification
	# [http://www.iptc.org/std/IIM/4.1/specification/IIMV4.1.pdf], the format
	# for a string field representing a time is '%H%M%S±%H%M'.
	# However, the string returned by exiv2 using method TimeValue::toString()
	# is formatted using pattern '%H:%M:%S±%H:%M'.

	if len(string) != 14:
		# the string is not correctly formatted, do nothing
		return string

	if (string[2] != ':') or (string[5] != ':') or (string[11] != ':'):
		# the string is not correctly formatted, do nothing
		return string

	offsetSign = string[8]
	if (offsetSign != '+') and (offsetSign != '-'):
		# the string is not correctly formatted, do nothing
		return string

	try:
		hours = int(string[:2])
		minutes = int(string[3:5])
		seconds = int(string[6:8])
		offsetHours = int(string[9:11])
		offsetMinutes = int(string[12:])
	except ValueError:
		# the string is not correctly formatted, do nothing
		return string

	try:
		offset = FixedOffset(offsetSign, offsetHours, offsetMinutes)
		localTime = datetime.time(hours, minutes, seconds, tzinfo=offset)
	except ValueError:
		# the values are out of range, do nothing
		return string

	return localTime

class Rational:

	"""
	A class representing a rational number.
	"""

	def __init__(self, numerator, denominator):
		"""
		Constructor.

		Construct a rational number from its numerator and its denominator.

		Keyword arguments:
		numerator -- the numerator
		denominator -- the denominator (if zero, will raise a ZeroDivisionError)
		"""
		if int(denominator) == 0:
			raise ZeroDivisionError('Denominator of a rational number cannot be zero')
		self.numerator = long(numerator)
		self.denominator = long(denominator)

	def __eq__(self, other):
		"""
		Compare two rational numbers for equality.

		Two rational numbers are equal if and only if their numerators are equal
		and their denominators are equal.

		Keyword arguments:
		other -- the rational number to compare to self for equality
		"""
		return ((self.numerator == other.numerator) and
		        (self.denominator == other.denominator))

	def __str__(self):
		"""
		Return a string representation of the rational number.
		"""
		return str(self.numerator) + '/' + str(self.denominator)

def StringToRational(string):
	"""
	Try to convert a string containing a rational number to a Rational object.

	Try to convert a string containing a rational number to the corresponding
	Rational object.
	The conversion is done by matching a regular expression.
	If the pattern does not match, the Rational object with numerator=0 and
	denominator=1 is returned.

	Keyword arguments:
	string -- the string potentially containing a rational number
	"""
	pattern = re.compile("(-?[0-9]+)/(-?[1-9][0-9]*)")
	match = pattern.match(string)
	if match == None:
		return Rational(0, 1)
	else:
		return Rational(*map(long, match.groups()))

def ConvertToPythonType(tagFamily, tagType, tagValue):
	"""
	Types a tag value using Python's built-in types or modules.

	Whenever possible, the value is typed using Python's built-in types or
	modules such as date when the value represents a date (e.g. the IPTC tag
	'Iptc.Application2.DateCreated').
	For EXIF rational number, custom type pyexiv2.Rational is used.

	Keyword arguments:
	tagFamily -- the family of the tag ('Exif' or 'Iptc')
	tagType -- the type of the tag as defined in the EXIF and IPTC specifications
	tagValue -- the value of the tag as a raw string
	"""
	value = tagValue
	if tagFamily == 'Exif':
		if tagType == 'Byte':
			pass
		elif tagType == 'Ascii':
			# try to guess if the value is a datetime
			value = StringToDateTime(tagValue)
		elif tagType == 'Short':
			value = int(tagValue)
		elif tagType == 'Long' or tagType == 'SLong':
			value = long(tagValue)
		elif tagType == 'Rational' or tagType == 'SRational':
			value = StringToRational(tagValue)
		elif tagType == 'Undefined':
			# tagValue is a sequence of bytes whose codes are written as a
			# string, each code being followed by a blank space (e.g.
			# "48 50 50 49 " for "0221").
			try:
				value = UndefinedToString(tagValue)
			except ValueError:
				# Some tags such as "Exif.Photo.UserComment" are marked as
				# Undefined but do not store their value as expected.
				# This should fix bug #173387.
				pass
	elif tagFamily == 'Iptc':
		if tagType == 'Short':
			value = int(tagValue)
		elif tagType == 'String':
			pass
		elif tagType == 'Date':
			value = StringToDate(tagValue)
		elif tagType == 'Time':
			value = StringToTime(tagValue)
		elif tagType == 'Undefined':
			pass
	return value

class Image(libpyexiv2.Image):

	"""
	Provide convenient methods for the manipulation of EXIF and IPTC metadata.

	Provide convenient methods for the manipulation of EXIF and IPTC metadata
	embedded in image files such as JPEG and TIFF files, using Python's built-in
	types and modules such as datetime.
	"""

	def __init__(self, filename):
		if filename.__class__ is unicode:
			filename = filename.encode('utf-8')
		libpyexiv2.Image.__init__(self, filename)
		self.__exifTagsDict = {}
		self.__iptcTagsDict = {}
		self.__exifCached = False
		self.__iptcCached = False

	def __getExifTagValue(self, key):
		"""
		Get the value associated to a key in EXIF metadata.

		Get the value associated to a key in EXIF metadata.
		Whenever possible, the value is typed using Python's built-in types or
		modules such as datetime when the value is composed of a date and a time
		(e.g. the EXIF tag 'Exif.Photo.DateTimeOriginal').

		Keyword arguments:
		key -- the EXIF key of the requested metadata tag
		"""
		tagType, tagValue = self.__getExifTag(key)
		if tagType not in ('Byte', 'Ascii', 'Undefined'):
			values = [ConvertToPythonType('Exif', tagType, x) for x in tagValue.split()]
			if len(values) == 1:
				return values[0]
			else:
				return tuple(values)
		else:
			return ConvertToPythonType('Exif', tagType, tagValue)

	def __setExifTagValue(self, key, value):
		"""
		Set the value associated to a key in EXIF metadata.

		Set the value associated to a key in EXIF metadata.
		The new value passed should be typed using Python's built-in types or
		modules such as datetime when the value is composed of a date and a time
		(e.g. the EXIF tag 'Exif.Photo.DateTimeOriginal'), the method takes care
		of converting it before setting the internal EXIF tag value.

		Keyword arguments:
		key -- the EXIF key of the requested metadata tag
		value -- the new value for the requested metadata tag
		"""
		valueType = value.__class__
		if valueType == int or valueType == long:
			strVal = str(value)
		elif valueType == datetime.datetime:
			strVal = value.strftime('%Y:%m:%d %H:%M:%S')
		elif valueType == list or valueType == tuple:
			strVal = ' '.join([str(x) for x in value])
		else:
			# Value must already be a string.
			# Warning: no distinction is possible between values that really are
			# strings (type 'Ascii') and those that are supposed to be sequences
			# of bytes (type 'Undefined'), in which case value must be passed as
			# a string correctly formatted, using utility function
			# StringToUndefined().
			strVal = str(value)
		typeName, oldValue = self.__setExifTag(key, strVal)
		return typeName

	def __getIptcTagValue(self, key):
		"""
		Get the value(s) associated to a key in IPTC metadata.

		Get the value associated to a key in IPTC metadata.
		Whenever possible, the value is typed using Python's built-in types or
		modules such as date when the value represents a date (e.g. the IPTC tag
		'Iptc.Application2.DateCreated').
		If key represents a repeatable tag, a list of several values is
		returned. If not, or if it has only one repetition, the list simply has
		one element.

		Keyword arguments:
		key -- the IPTC key of the requested metadata tag
		"""
		return [ConvertToPythonType('Iptc', *x) for x in self.__getIptcTag(key)]

	def __setIptcTagValue(self, key, value, index=0):
		"""
		Set the value associated to a key in IPTC metadata.

		Set the value associated to a key in IPTC metadata.
		The new value passed should be typed using Python's built-in types or
		modules such as datetime when the value contains a date or a time
		(e.g. the IPTC tags 'Iptc.Application2.DateCreated' and
		'Iptc.Application2.TimeCreated'), the method takes care
		of converting it before setting the internal IPTC tag value.
		If key references a repeatable tag, the parameter index (starting from
		0 like a list index) is used to determine which of the repetitions is to
		be set. In case of an index greater than the highest existing one, adds
		a repetition of the tag. index defaults to 0 for (the majority of)
		non-repeatable tags.

		Keyword arguments:
		key -- the IPTC key of the requested metadata tag
		value -- the new value for the requested metadata tag
		index -- the index of the tag repetition to set (default value: 0)
		"""
		if (index < 0):
			raise IndexError('Index must be greater than or equal to zero')
		valueType = value.__class__
		if valueType == int or valueType == long:
			strVal = str(value)
		elif valueType == datetime.date:
			strVal = value.strftime('%Y-%m-%d')
		elif valueType == datetime.time:
			# The only legal format for a time is '%H:%M:%S±%H:%M',
			# but if the UTC offset is absent (format '%H:%M:%S'), the time can
			# still be set (exiv2 is permissive).
			strVal = value.strftime('%H:%M:%S%Z')
		else:
			# Value must already be a string.
			# Warning: no distinction is possible between values that really are
			# strings (type 'String') and those that are of type 'Undefined'.
			# FIXME: for tags of type 'Undefined', this does not seem to work...
			strVal = str(value)
		typeName, oldValue = self.__setIptcTag(key, strVal, index)
		return typeName

	def __getitem__(self, key):
		"""
		Read access implementation of the [] operator on Image objects.

		Get the value associated to a key in EXIF/IPTC metadata.
		The value is cached in an internal dictionary for later accesses.

		Whenever possible, the value is typed using Python's built-in types or
		modules such as datetime when the value is composed of a date and a time
		(e.g. the EXIF tag 'Exif.Photo.DateTimeOriginal') or date when the value
		represents a date (e.g. the IPTC tag 'Iptc.Application2.DateCreated').

		If key references a repeatable tag (IPTC only), a list of several values
		is returned. If not, or if it has only one repetition, the list simply
		has one element.

		Keyword arguments:
		key -- the [EXIF|IPTC] key of the requested metadata tag
		"""
		if key.__class__ is not str:
			raise TypeError('Key must be of type string')
		tagFamily = key[:4]
		if tagFamily == 'Exif':
			try:
				return self.__exifTagsDict[key]
			except KeyError:
				value = self.__getExifTagValue(key)
				self.__exifTagsDict[key] = value
				return value
		elif tagFamily == 'Iptc':
			try:
				return self.__iptcTagsDict[key]
			except KeyError:
				value = self.__getIptcTagValue(key)
				if len(value) == 1:
					value = value[0]
				elif len(value) > 1:
					value = tuple(value)
				self.__iptcTagsDict[key] = value
				return value
		else:
			# This is exiv2's standard error message, all futures changes on
			# exiv2's side should be reflected here.
			# As a future development, consider i18n for error messages. 
			raise IndexError("Invalid key `" + key + "'")

	def __setitem__(self, key, value):
		"""
		Write access implementation of the [] operator on Image objects.

		Set the value associated to a key in EXIF/IPTC metadata.
		The value is cached in an internal dictionary for later accesses.

		The new value passed should be typed using Python's built-in types or
		modules such as datetime when the value contains a date and a time
		(e.g. the EXIF tag 'Exif.Photo.DateTimeOriginal' or the IPTC tags
		'Iptc.Application2.DateCreated' and 'Iptc.Application2.TimeCreated'),
		the method takes care of converting it before setting the internal tag
		value.

		If key references a repeatable tag (IPTC only), value can be a list of
		values (the new values will overwrite the old ones, and an empty list of
		values will unset the tag).

		Keyword arguments:
		key -- the [EXIF|IPTC] key of the requested metadata tag
		value -- the new value for the requested metadata tag
		"""
		if key.__class__ is not str:
			raise TypeError('Key must be of type string')
		tagFamily = key[:4]
		if tagFamily == 'Exif':
			if value is not None:
				# For datetime objects, microseconds are not supported by the
				# EXIF specification, so truncate them if present.
				if value.__class__ is datetime.datetime:
					value = value.replace(microsecond=0)

				typeName = self.__setExifTagValue(key, value)
				self.__exifTagsDict[key] = ConvertToPythonType(tagFamily, typeName, str(value))
			else:
				self.__deleteExifTag(key)
				if self.__exifTagsDict.has_key(key):
					del self.__exifTagsDict[key]
		elif tagFamily == 'Iptc':
			# The case of IPTC tags is a bit trickier since some tags are
			# repeatable. To simplify the process, parameter 'value' is
			# transformed into a tuple if it is not already one and then each of
			# its values is processed (set, that is) in a loop.
			newValues = value
			if newValues is None:
				# Setting the value to None does not really make sense, but can
				# in a way be seen as equivalent to deleting it, so this
				# behaviour is simulated by providing an empty list for 'value'.
				newValues = ()
			if newValues.__class__ is not tuple:
				if newValues.__class__ is list:
					# For flexibility, passing a list instead of a tuple works
					newValues = tuple(newValues)
				else:
					# Interpret the value as a single element
					newValues = (newValues,)
			try:
				oldValues = self.__iptcTagsDict[key]
				if oldValues.__class__ is not tuple:
					oldValues = (oldValues,)
			except KeyError:
				# The tag is not cached yet
				try:
					oldValues = self.__getitem__(key)
				except KeyError:
					# The tag is not set
					oldValues = ()

			# For time objects, microseconds are not supported by the IPTC
			# specification, so truncate them if present.
			tempNewValues = []
			for newValue in newValues:
				if newValue.__class__ is datetime.time:
					tempNewValues.append(newValue.replace(microsecond=0))
				else:
					tempNewValues.append(newValue)
			newValues = tuple(tempNewValues)

			# This loop processes the values one by one. There are 3 cases:
			#   * if the two tuples are of the exact same size, each item in
			#     oldValues is replaced by its new value in newValues;
			#   * if newValues is longer than oldValues, each item in oldValues
			#     is replaced by its new value in newValues and the new items
			#     are appended at the end of oldValues;
			#   * if newValues is shorter than oldValues, each item in newValues
			#     replaces the corresponding one in oldValues and the trailing
			#     extra items in oldValues are deleted.
			for i in xrange(max(len(oldValues), len(newValues))):
				try:
					typeName = self.__setIptcTagValue(key, newValues[i], i)
				except IndexError:
					try:
						self.__deleteIptcTag(key, min(len(oldValues), len(newValues)))
					except KeyError:
						pass
			if len(newValues) > 0:
				if len(newValues) == 1:
					newValues = newValues[0]
				self.__iptcTagsDict[key] = tuple([ConvertToPythonType(tagFamily, typeName, str(v)) for v in newValues])
			else:
				if self.__iptcTagsDict.has_key(key):
					del self.__iptcTagsDict[key]
		else:
			raise IndexError("Invalid key `" + key + "'")

	def __delitem__(self, key):
		"""
		Implementation of the del operator for deletion on Image objects.

		Delete the value associated to a key in EXIF/IPTC metadata.

		If key references a repeatable tag (IPTC only), all the associated
		values will be deleted.

		Keyword arguments:
		key -- the [EXIF|IPTC] key of the requested metadata tag
		"""
		if key.__class__ is not str:
			raise TypeError('Key must be of type string')
		tagFamily = key[:4]
		if tagFamily == 'Exif':
			self.__deleteExifTag(key)
			if self.__exifTagsDict.has_key(key):
				del self.__exifTagsDict[key]
		elif tagFamily == 'Iptc':
			try:
				oldValues = self.__iptcTagsDict[key]
			except KeyError:
				oldValues = self.__getIptcTag(key)
			for i in xrange(len(oldValues)):
				self.__deleteIptcTag(key, 0)
			if self.__iptcTagsDict.has_key(key):
				del self.__iptcTagsDict[key]
		else:
			raise IndexError("Invalid key `" + key + "'")

	def cacheAllExifTags(self):
		"""
		Cache the EXIF tag values for faster subsequent access.

		Read the values of all the EXIF tags in the image and cache them in an
		internal dictionary so as to speed up subsequent accesses.
		"""
		if not self.__exifCached:
			for key in self.exifKeys():
				self[key]
			self.__exifCached = True

	def cacheAllIptcTags(self):
		"""
		Cache the IPTC tag values for faster subsequent access.

		Read the values of all the IPTC tags in the image and cache them in an
		internal dictionary so as to speed up subsequent accesses.
		"""
		if not self.__iptcCached:
			for key in self.iptcKeys():
				self[key]
			self.__iptcCached = True

	def interpretedExifValue(self, key):
		"""
		Get the interpreted value of an EXIF tag as presented by the exiv2 tool.

		For EXIF tags, the exiv2 command-line tool is capable of displaying
		user-friendly interpreted values, such as 'top, left' for the
		'Exif.Image.Orientation' tag when it has value '1'. This method always
		returns a string containing this interpreted value for a given tag.
		Warning: calling this method will not cache the value in the internal
		dictionary.

		Keyword arguments:
		key -- the EXIF key of the requested metadata tag
		"""
		# This method was added as a requirement tracked by bug #147534
		return self.__getExifTagToString(key)

	def copyMetadataTo(self, destImage):
		"""
		Duplicate all the tags and the comment from this image to another one.

		Read all the values of the EXIF and IPTC tags and the comment and write
		them back to the new image.

		Keyword arguments:
		destImage -- the destination image to write the copied metadata back to
		"""
		for key in self.exifKeys():
			destImage[key] = self[key]
		for key in self.iptcKeys():
			destImage[key] = self[key]
		destImage.setComment(self.getComment())

def _test():
	print 'testing library pyexiv2...'
	# TODO: various tests
	print 'done.'

if __name__ == '__main__':
	_test()

