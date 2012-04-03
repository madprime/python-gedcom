#
# Gedcom 5.5 Parser
#
# Copyright (C) 2012 Madeleine Price Ball
# Copyright (C) 2005 Daniel Zappala (zappala [ at ] cs.byu.edu)
# Copyright (C) 2005 Brigham Young University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# Please see the GPL license at http://www.gnu.org/licenses/gpl.txt
#
# This code based on work from Zappala, 2005.
# To contact the Zappala, see http://faculty.cs.byu.edu/~zappala

__all__ = ["Gedcom", "Element", "GedcomParseError"]

# Global imports
import re

class Gedcom:
    """Parses and manipulates GEDCOM 5.5 format data

    For documentation of the GEDCOM 5.5 format, see:
    http://homepages.rootsweb.ancestry.com/~pmcbride/gedcom/55gctoc.htm

    This parser reads and parses a GEDCOM file.
    Elements may be accessed via:
      - a list (all elements, default order is same as in file)
      - a dict (only elements with pointers, which are the keys)
    """

    def __init__(self, filepath):
        """ Initialize a GEDCOM data object. You must supply a Gedcom file."""
        self.__element_list = []
        self.__element_dict = {}
        self.__element_top = Element(-1, "", "TOP", "", self.__element_dict)
        self.__parse(filepath)

    def element_list(self):
        """ Return a list of all the elements in the Gedcom file.

        By default elements are in the same order as they appeared in the file.
        """
        return self.__element_list

    def element_dict(self):
        """Return a dictionary of elements from the Gedcom file.

        Only elements identified by a pointer are listed in the dictionary.
        The keys for the dictionary are the pointers.
        """
        return self.__element_dict

    # Private methods

    def __parse(self, filepath):
        """Open and parse file path as GEDCOM 5.5 formatted data."""
        gedcom_file = open(filepath)
        line_num = 1
        last_elem = self.__element_top
        for line in gedcom_file:
            last_elem = self.__parse_line(line_num, line, last_elem)
            line_num += 1

    def __parse_line(self, line_num, line, last_elem):
        """Parse a line from a GEDCOM 5.5 formatted document.

        Each line should have the following (bracketed items optional):
        level + ' ' + [pointer + ' ' +] tag + [' ' + line_value]
        """
        ged_line_re = (
            # Level must start with nonnegative int, no leading zeros.
            '^(0|[1-9]+[0-9]*) ' +
            # Pointer optional, if it exists it must be flanked by '@'
            '(@[^@]+@ |)' +
            # Tag must be alphanumeric string
            '([A-Za-z0-9_]+)' +
            # Value optional, consists of anything after a space to end of line
            '( .*|)$'
            )
        if re.match(ged_line_re, line):
            line_parts = re.match(ged_line_re, line).groups()
        else:
            errmsg = ("Line %d of document violates GEDCOM format" % line_num +
                      "\nSee: http://homepages.rootsweb.ancestry.com/" +
                      "~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(errmsg)

        level = int(line_parts[0])
        pointer = line_parts[1].rstrip(' ')
        tag = line_parts[2]
        value = line_parts[3].lstrip(' ')

        # Check level: should never be more than one higher than previous line.
        if level > last_elem.level() + 1:
            errmsg = ("Line %d of document violates GEDCOM format" % line_num +
                      "\nLines must be no more than one level higher than " +
                      "previous line.\nSee: http://homepages.rootsweb." +
                      "ancestry.com/~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(errmsg)

        # Create element. Store in list and dict, create children and parents.
        element = Element(level, pointer, tag, value, self.__element_dict)
        self.__element_list.append(element)
        if pointer != '':
            self.__element_dict[pointer] = element

        # Start with last element as parent, back up if necessary.
        parent_elem = last_elem
        while parent_elem.level() > level - 1:
            parent_elem = parent_elem.parent()
        # Add child to parent & parent to child.
        parent_elem.add_child(element)
        element.add_parent(parent_elem)
        return element

    # Methods for analyzing relationships between individuals

    def families(self, individual, family_type="FAMS"):
        """ Return family elements listed for an individual. 

        family_type can be FAMS (families where the individual is a spouse) or
        FAMC (families where the individual is a child). If a value is not
        provided, FAMS is default value.
        """
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        families = []
        for child in individual.children():
            is_fams = (child.tag() == family_type and
                       child.value() in self.__element_dict and
                       self.__element_dict[child.value()].is_family())
            if is_fams:
                families.append(self.__element_dict[child.value()])
        return families

    # Other methods

    def print_gedcom(self):
        """Write GEDCOM data to stdout."""
        for element in self.element_list():
            print element


class GedcomParseError(Exception):
    """ Exception raised when a Gedcom parsing error occurs
    """
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return `self.value`

class Element:
    """ Gedcom element

    Each line in a Gedcom file is an element with the format

    level [pointer] tag [value]

    where level and tag are required, and pointer and value are
    optional.  Elements are arranged hierarchically according to their
    level, and elements with a level of zero are at the top level.
    Elements with a level greater than zero are children of their
    parent.

    A pointer has the format @pname@, where pname is any sequence of
    characters and numbers.  The pointer identifies the object being
    pointed to, so that any pointer included as the value of any
    element points back to the original object.  For example, an
    element may have a FAMS tag whose value is @F1@, meaning that this
    element points to the family record in which the associated person
    is a spouse.  Likewise, an element with a tag of FAMC has a value
    that points to a family record in which the associated person is a
    child.
    
    See a Gedcom file for examples of tags and their values.

    """

    def __init__(self,level,pointer,tag,value,dict):
        """ Initialize an element.  You must include a level, pointer,
        tag, value, and global element dictionary.  Normally initialized
        by the Gedcom parser, not by a user.
        """
        # basic element info
        self.__level = level
        self.__pointer = pointer
        self.__tag = tag
        self.__value = value
        self.__dict = dict
        # structuring
        self.__children = []
        self.__parent = None

    def level(self):
        """ Return the level of this element """
        return self.__level

    def pointer(self):
        """ Return the pointer of this element """
        return self.__pointer
    
    def tag(self):
        """ Return the tag of this element """
        return self.__tag

    def value(self):
        """ Return the value of this element """
        return self.__value

    def children(self):
        """ Return the child elements of this element """
        return self.__children

    def parent(self):
        """ Return the parent element of this element """
        return self.__parent

    def add_child(self,element):
        """ Add a child element to this element """
        self.children().append(element)
        
    def add_parent(self,element):
        """ Add a parent element to this element """
        self.__parent = element

    def is_individual(self):
        """ Check if this element is an individual """
        return self.tag() == "INDI"

    def is_family(self):
        """ Check if this element is a family """
        return self.tag() == "FAM"

    # criteria matching

    def criteria_match(self,criteria):
        """ Check in this element matches all of the given criteria.
        The criteria is a colon-separated list, where each item in the

        list has the form [name]=[value]. The following criteria are supported:

        surname=[name]
             Match a person with [name] in any part of the surname.
        name=[name]
             Match a person with [name] in any part of the given name.
        birth=[year]
             Match a person whose birth year is a four-digit [year].
        birthrange=[year1-year2]
             Match a person whose birth year is in the range of years from
             [year1] to [year2], including both [year1] and [year2].
        death=[year]
        deathrange=[year1-year2]
        marriage=[year]
        marriagerange=[year1-year2]

        """

        # error checking on the criteria
        try:
            for crit in criteria.split(':'):
                key,value = crit.split('=')
        except:
            return False
        match = True
        for crit in criteria.split(':'):
            key,value = crit.split('=')
            if key == "surname" and not self.surname_match(value):
                match = False
            elif key == "name" and not self.given_match(value):
                match = False
            elif key == "birth":
                try:
                    year = int(value)
                    if not self.birth_year_match(year):
                        match = False
                except:
                    match = False
            elif key == "birthrange":
                try:
                    year1,year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.birth_range_match(year1,year2):
                        match = False
                except:
                    match = False
            elif key == "death":
                try:
                    year = int(value)
                    if not self.death_year_match(year):
                        match = False
                except:
                    match = False
            elif key == "deathrange":
                try:
                    year1,year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.death_range_match(year1,year2):
                        match = False
                except:
                    match = False
            elif key == "marriage":
                try:
                    year = int(value)
                    if not self.marriage_year_match(year):
                        match = False
                except:
                    match = False
            elif key == "marriagerange":
                try:
                    year1,year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.marriage_range_match(year1,year2):
                        match = False
                except:
                    match = False
                    
        return match

    def surname_match(self,name):
        """ Match a string with the surname of an individual """
        (first,last) = self.name()
        return last.find(name) >= 0

    def given_match(self,name):
        """ Match a string with the given names of an individual """
        (first,last) = self.name()
        return first.find(name) >= 0

    def birth_year_match(self,year):
        """ Match the birth year of an individual.  Year is an integer. """
        return self.birth_year() == year

    def birth_range_match(self,year1,year2):
        """ Check if the birth year of an individual is in a given range.
        Years are integers.
        """
        year = self.birth_year()
        if year >= year1 and year <= year2:
            return True
        return False

    def death_year_match(self,year):
        """ Match the death year of an individual.  Year is an integer. """
        return self.death_year() == year

    def death_range_match(self,year1,year2):
        """ Check if the death year of an individual is in a given range.
        Years are integers.
        """
        year = self.death_year()
        if year >= year1 and year <= year2:
            return True
        return False

    def marriage_year_match(self,year):
        """ Check if one of the marriage years of an individual matches
        the supplied year.  Year is an integer. """
        years = self.marriage_years()
        return year in years

    def marriage_range_match(self,year1,year2):
        """ Check if one of the marriage year of an individual is in a
        given range.  Years are integers.
        """
        years = self.marriage_years()
        for year in years:
            if year >= year1 and year <= year2:
                return True
        return False

    def name(self):
        """ Return a person's names as a tuple: (first,last) """
        first = ""
        last = ""
        if not self.is_individual():
            return (first,last)
        for e in self.children():
            if e.tag() == "NAME":
                # some older Gedcom files don't use child tags but instead
                # place the name in the value of the NAME tag
                if e.value() != "":
                    name = e.value.split('/')
                    first = name[0].strip()
                    last = name[1].strip()
                else:
                    for c in e.children():
                        if c.tag() == "GIVN":
                            first = c.value()
                        if c.tag() == "SURN":
                            last = c.value()
        return (first,last)

    def birth(self):
        """ Return the birth tuple of a person as (date,place) """
        date = ""
        place = ""
        if not self.is_individual():
            return (date,place)
        for e in self.children():
            if e.tag() == "BIRT":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
                    if c.tag() == "PLAC":
                        place = c.value()
        return (date,place)

    def birth_year(self):
        """ Return the birth year of a person in integer format """
        date = ""
        if not self.is_individual():
            return date
        for e in self.children():
            if e.tag() == "BIRT":
                for c in e.children():
                    if c.tag() == "DATE":
                        datel = c.value().split()
                        date = datel[len(datel)-1]
        if date == "":
            return -1
        try:
            return int(date)
        except:
            return -1

    def death(self):
        """ Return the death tuple of a person as (date,place) """
        date = ""
        place = ""
        if not self.is_individual():
            return (date,place)
        for e in self.children():
            if e.tag() == "DEAT":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
                    if c.tag() == "PLAC":
                        place = c.value()
        return (date,place)

    def death_year(self):
        """ Return the death year of a person in integer format """
        date = ""
        if not self.is_individual():
            return date
        for e in self.children():
            if e.tag() == "DEAT":
                for c in e.children():
                    if c.tag() == "DATE":
                        datel = c.value().split()
                        date = datel[len(datel)-1]
        if date == "":
            return -1
        try:
            return int(date)
        except:
            return -1

    def deceased(self):
        """ Check if a person is deceased """
        if not self.is_individual():
            return False
        for e in self.children():
            if e.tag() == "DEAT":
                return True
        return False

    def marriage(self):
        """ Return a list of marriage tuples for a person, each listing
        (date,place).
        """
        date = ""
        place = ""
        if not self.is_individual():
            return (date,place)
        for e in self.children():
            if e.tag() == "FAMS":
                f = self.__dict.get(e.value(),None)
                if f == None:
                    return (date,place)
                for g in f.children():
                    if g.tag() == "MARR":
                        for h in g.children():
                            if h.tag() == "DATE":
                                date = h.value()
                            if h.tag() == "PLAC":
                                place = h.value()
        return (date,place)

    def marriage_years(self):
        """ Return a list of marriage years for a person, each in integer
        format.
        """
        dates = []
        if not self.is_individual():
            return dates
        for e in self.children():
            if e.tag() == "FAMS":
                f = self.__dict.get(e.value(),None)
                if f == None:
                    return dates
                for g in f.children():
                    if g.tag() == "MARR":
                        for h in g.children():
                            if h.tag() == "DATE":
                                datel = h.value().split()
                                date = datel[len(datel)-1]
                                try:
                                    dates.append(int(date))
                                except:
                                    pass
        return dates

    def get_individual(self):
        """ Return this element and all of its sub-elements """
        result = str(self)
        for e in self.children():
            result += '\n' + e.get_individual()
        return result

    def get_family(self):
        result = self.get_individual()
        for e in self.children():
            if e.tag() == "HUSB" or e.tag() == "WIFE" or e.tag() == "CHIL":
                f = self.__dict.get(e.value())
                if f != None:
                    result += '\n' + f.get_individual()
        return result

    def __str__(self):
        """ Format this element as its original string """
        result = str(self.level())
        if self.pointer() != "":
            result += ' ' + self.pointer()
        result += ' ' + self.tag()
        if self.value() != "":
            result += ' ' + self.value()
        return result
