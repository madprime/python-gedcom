#
# Gedcom 5.5 Parser
#
# Copyright (C) 2018 Nicklas Reincke (contact [ at ] reynke.com)
# Copyright (C) 2016 Andreas Oberritter
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
import re as regex
from sys import version_info


class Gedcom:
    """Parses and manipulates GEDCOM 5.5 format data

    For documentation of the GEDCOM 5.5 format, see:
    http://homepages.rootsweb.ancestry.com/~pmcbride/gedcom/55gctoc.htm

    This parser reads and parses a GEDCOM file.
    Elements may be accessed via:
      - a list (all elements, default order is same as in file)
      - a dict (only elements with pointers, which are the keys)
    """

    def __init__(self, file_path):
        """ Initialize a GEDCOM data object. You must supply a GEDCOM file."""
        self.__element_list = []
        self.__element_dict = {}
        self.invalidate_cache()
        self.__element_top = Element(-1, "", "TOP", "")
        self.__parse(file_path)

    def invalidate_cache(self):
        """ Cause element_list() and element_dict() to return updated data.

        The update gets deferred until each of the methods actually gets called.
        """
        self.__element_list = []
        self.__element_dict = {}

    def element_list(self):
        """ Return a list of all the elements in the Gedcom file.

        By default elements are in the same order as they appeared in the file.

        This list gets generated on-the-fly, but gets cached. If the database
        was modified, you should call invalidate_cache() once to let this
        method return updated data.

        Consider using root() or records() to access the hierarchical GEDCOM
        tree, unless you rarely modify the database.
        """
        if not self.__element_list:
            for element in self.records():
                self.__build_list(element, self.__element_list)
        return self.__element_list

    def element_dict(self):
        """Return a dictionary of elements from the Gedcom file.

        Only elements identified by a pointer are listed in the dictionary.
        The keys for the dictionary are the pointers.

        This dictionary gets generated on-the-fly, but gets cached. If the
        database was modified, you should call invalidate_cache() once to let
        this method return updated data.
        """
        if not self.__element_dict:
            self.__element_dict = {element.pointer(): element for element in self.records() if element.pointer()}
        return self.__element_dict

    def root(self):
        """ Returns a virtual root element containing all logical records as children

        When printed, this element converts to an empty string.
        """
        return self.__element_top

    def records(self):
        """ Return a list of logical records in the GEDCOM file.

        By default, elements are in the same order as they appeared in the file.
        """
        return self.root().children()

    # Private methods

    def __parse(self, file_path):
        """Open and parse file path as GEDCOM 5.5 formatted data."""
        gedcom_file = open(file_path, 'rb')
        line_number = 1
        last_element = self.__element_top
        for line in gedcom_file:
            last_element = self.__parse_line(line_number, line.decode('utf-8'), last_element)
            line_number += 1

    def __parse_line(self, line_num, line, last_elem):
        """Parse a line from a GEDCOM 5.5 formatted document.

        Each line should have the following (bracketed items optional):
        level + ' ' + [pointer + ' ' +] tag + [' ' + line_value]
        """
        ged_line_regex = (
            # Level must start with nonnegative int, no leading zeros.
                '^(0|[1-9]+[0-9]*) ' +
                # Pointer optional, if it exists it must be flanked by '@'
                '(@[^@]+@ |)' +
                # Tag must be alphanumeric string
                '([A-Za-z0-9_]+)' +
                # Value optional, consists of anything after a space to end of line
                '( [^\n\r]*|)' +
                # End of line defined by \n or \r
                '([\r\n]{1,2})'
        )
        if regex.match(ged_line_regex, line):
            line_parts = regex.match(ged_line_regex, line).groups()
        else:
            error_message = ("Line %d of document violates GEDCOM format" % line_num +
                             "\nSee: http://homepages.rootsweb.ancestry.com/" +
                             "~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(error_message)

        level = int(line_parts[0])
        pointer = line_parts[1].rstrip(' ')
        tag = line_parts[2]
        value = line_parts[3][1:]
        crlf = line_parts[4]

        # Check level: should never be more than one higher than previous line.
        if level > last_elem.level() + 1:
            error_message = ("Line %d of document violates GEDCOM format" % line_num +
                             "\nLines must be no more than one level higher than " +
                             "previous line.\nSee: http://homepages.rootsweb." +
                             "ancestry.com/~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(error_message)

        # Create element. Store in list and dict, create children and parents.
        element = Element(level, pointer, tag, value, crlf, multi_line=False)

        # Start with last element as parent, back up if necessary.
        parent_elem = last_elem
        while parent_elem.level() > level - 1:
            parent_elem = parent_elem.parent()
        # Add child to parent & parent to child.
        parent_elem.add_child(element)
        return element

    def __build_list(self, element, element_list):
        """ Recursively add Elements to a list containing elements. """
        element_list.append(element)
        for child in element.children():
            self.__build_list(child, element_list)

    # Methods for analyzing individuals and relationships between individuals

    def marriages(self, individual):
        """ Return list of marriage tuples (date, place) for an individual. """
        marriages = []
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        families = self.families(individual, "FAMS")
        for family in families:
            for family_data in family.children():
                if family_data.tag() == "MARR":
                    for marriage_data in family_data.children():
                        date = ''
                        place = ''
                        if marriage_data.tag() == "DATE":
                            date = marriage_data.value()
                        if marriage_data.tag() == "PLAC":
                            place = marriage_data.value()
                        marriages.append((date, place))
        return marriages

    def marriage_years(self, individual):
        """ Return list of marriage years (as int) for an individual. """
        dates = []
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        families = self.families(individual, "FAMS")
        for family in families:
            for family_data in family.children():
                if family_data.tag() == "MARR":
                    for marriage_data in family_data.children():
                        if marriage_data.tag() == "DATE":
                            date = marriage_data.value().split()[-1]
                            try:
                                dates.append(int(date))
                            except ValueError:
                                pass
        return dates

    def marriage_year_match(self, individual, year):
        """ Check if one of the marriage years of an individual matches
        the supplied year.  Year is an integer. """
        years = self.marriage_years(individual)
        return year in years

    def marriage_range_match(self, individual, year1, year2):
        """ Check if one of the marriage year of an individual is in a
        given range.  Years are integers.
        """
        years = self.marriage_years(individual)
        for year in years:
            if year1 <= year <= year2:
                return True
        return False

    def families(self, individual, family_type="FAMS"):
        """ Return family elements listed for an individual. 

        family_type can be FAMS (families where the individual is a spouse) or
        FAMC (families where the individual is a child). If a value is not
        provided, FAMS is default value.
        """
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        families = []
        element_dict = self.element_dict()
        for child in individual.children():
            is_family = (child.tag() == family_type and
                         child.value() in element_dict and
                         element_dict[child.value()].is_family())
            if is_family:
                families.append(element_dict[child.value()])
        return families

    def get_ancestors(self, individual, anc_type="ALL"):
        """ Return elements corresponding to ancestors of an individual

        Optional anc_type. Default "ALL" returns all ancestors, "NAT" can be
        used to specify only natural (genetic) ancestors.
        """
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = self.get_parents(individual, anc_type)
        ancestors = parents
        for parent in parents:
            ancestors = ancestors + self.get_ancestors(parent)
        return ancestors

    def get_parents(self, individual, parent_type="ALL"):
        """ Return elements corresponding to parents of an individual
        
        Optional parent_type. Default "ALL" returns all parents. "NAT" can be
        used to specify only natural (genetic) parents. 
        """
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = []
        families = self.families(individual, "FAMC")
        for family in families:
            if parent_type == "NAT":
                for family_member in family.children():
                    if family_member.tag() == "CHIL" and family_member.value() == individual.pointer():
                        for child in family_member.children():
                            if child.value() == "Natural":
                                if child.tag() == "_MREL":
                                    parents = (parents +
                                               self.get_family_members(family, "WIFE"))
                                elif child.tag() == "_FREL":
                                    parents = (parents +
                                               self.get_family_members(family, "HUSB"))
            else:
                parents = parents + self.get_family_members(family, "PARENTS")
        return parents

    def find_path_to_anc(self, desc, anc, path=None):
        """ Return path from descendant to ancestor. """
        if not desc.is_individual() and anc.is_individual():
            raise ValueError("Operation only valid for elements with IND tag.")
        if not path:
            path = [desc]
        if path[-1].pointer() == anc.pointer():
            return path
        else:
            parents = self.get_parents(desc, "NAT")
            for par in parents:
                potential_path = self.find_path_to_anc(par, anc, path + [par])
                if potential_path:
                    return potential_path
        return None

    def get_family_members(self, family, mem_type="ALL"):
        """Return array of family members: individual, spouse, and children.

        Optional argument mem_type can be used to return specific subsets.
        "ALL": Default, return all members of the family
        "PARENTS": Return individuals with "HUSB" and "WIFE" tags (parents)
        "HUSB": Return individuals with "HUSB" tags (father)
        "WIFE": Return individuals with "WIFE" tags (mother)
        "CHIL": Return individuals with "CHIL" tags (children)
        """
        if not family.is_family():
            raise ValueError("Operation only valid for elements with FAM tag.")
        family_members = []
        element_dict = self.element_dict()
        for elem in family.children():
            # Default is ALL
            is_family = (elem.tag() == "HUSB" or
                         elem.tag() == "WIFE" or
                         elem.tag() == "CHIL")
            if mem_type == "PARENTS":
                is_family = (elem.tag() == "HUSB" or
                             elem.tag() == "WIFE")
            elif mem_type == "HUSB":
                is_family = (elem.tag() == "HUSB")
            elif mem_type == "WIFE":
                is_family = (elem.tag() == "WIFE")
            elif mem_type == "CHIL":
                is_family = (elem.tag() == "CHIL")
            if is_family and elem.value() in element_dict:
                family_members.append(element_dict[elem.value()])
        return family_members

    # Other methods

    def print_gedcom(self):
        """Write GEDCOM data to stdout."""
        from sys import stdout
        self.save_gedcom(stdout)

    def save_gedcom(self, open_file):
        """ Save GEDCOM data to a file. """
        if version_info[0] >= 3:
            open_file.write(self.root().get_individual())
        else:
            open_file.write(self.root().get_individual().encode('utf-8'))


class GedcomParseError(Exception):
    """ Exception raised when a Gedcom parsing error occurs
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


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

    def __init__(self, level, pointer, tag, value, crlf="\n", multi_line=True):
        """ Initialize an element.  
        
        You must include a level, pointer, tag, and value. Normally 
        initialized by the Gedcom parser, not by a user.
        """
        # basic element info
        self.__level = level
        self.__pointer = pointer
        self.__tag = tag
        self.__value = value
        self.__crlf = crlf
        # structuring
        self.__children = []
        self.__parent = None
        if multi_line:
            self.set_multi_line_value(value)

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

    def set_value(self, value):
        """ Set the value of this element """
        self.__value = value

    def multi_line_value(self):
        """ Return the value of this element including continuations """
        result = self.value()
        last_crlf = self.__crlf
        for e in self.children():
            tag = e.tag()
            if tag == 'CONC':
                result += e.value()
                last_crlf = e.__crlf
            elif tag == 'CONT':
                result += last_crlf + e.value()
                last_crlf = e.__crlf
        return result

    def __avail_chars(self):
        n = len(self.__unicode__())
        if n > 255:
            return 0
        return 255 - n

    def __line_length(self, string):
        total = len(string)
        avail = self.__avail_chars()
        if total <= avail:
            return total

        spaces = 0
        while spaces < avail and string[avail - spaces - 1] == ' ':
            spaces = spaces + 1
        if spaces == avail:
            return avail
        return avail - spaces

    def __set_bounded_value(self, value):
        n = self.__line_length(value)
        self.set_value(value[:n])
        return n

    def __add_bounded_child(self, tag, value):
        c = self.new_child(tag)
        return c.__set_bounded_value(value)

    def __add_concatenation(self, string):
        index = 0
        size = len(string)
        while index < size:
            index = index + self.__add_bounded_child('CONC', string[index:])

    def set_multi_line_value(self, value):
        """ Set the value of this element, adding continuation lines as necessary. """
        self.set_value('')
        self.children()[:] = [c for c in self.children() if c.tag() not in ('CONC', 'CONT')]

        lines = value.splitlines()
        if lines:
            line = lines.pop(0)
            n = self.__set_bounded_value(line)
            self.__add_concatenation(line[n:])

            for line in lines:
                n = self.__add_bounded_child('CONT', line)
                self.__add_concatenation(line[n:])

    def children(self):
        """ Return the child elements of this element """
        return self.__children

    def parent(self):
        """ Return the parent element of this element """
        return self.__parent

    def new_child(self, tag, pointer='', value=''):
        """ Create and return a new child element of this element """
        c = Element(self.level() + 1, pointer, tag, value, self.__crlf)
        self.add_child(c)
        return c

    def add_child(self, element):
        """ Add a child element to this element """
        self.children().append(element)
        element.add_parent(self)

    def add_parent(self, element):
        """ Add a parent element to this element

        There's usually no need to call this method manually,
        add_child() calls it automatically.
        """
        self.__parent = element

    def is_individual(self):
        """ Check if this element is an individual """
        return self.tag() == "INDI"

    def is_family(self):
        """ Check if this element is a family """
        return self.tag() == "FAM"

    def is_file(self):
        """ Check if this element is a file """
        return self.tag() == "FILE"

    def is_object(self):
        """ Check if this element is an object """
        return self.tag() == "OBJE"

    # criteria matching

    def criteria_match(self, criteria):
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
        """

        # error checking on the criteria
        try:
            for criterion in criteria.split(':'):
                key, value = criterion.split('=')
        except:
            return False
        match = True
        for criterion in criteria.split(':'):
            key, value = criterion.split('=')
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
                    year1, year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.birth_range_match(year1, year2):
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
                    year1, year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.death_range_match(year1, year2):
                        match = False
                except:
                    match = False

        return match

    def surname_match(self, name):
        """ Match a string with the surname of an individual """
        (first, last) = self.name()
        return last.find(name) >= 0

    def given_match(self, name):
        """ Match a string with the given names of an individual """
        (first, last) = self.name()
        return first.find(name) >= 0

    def birth_year_match(self, year):
        """ Match the birth year of an individual.  Year is an integer. """
        return self.birth_year() == year

    def birth_range_match(self, year1, year2):
        """ Check if the birth year of an individual is in a given range.
        Years are integers.
        """
        year = self.birth_year()
        if year1 <= year <= year2:
            return True
        return False

    def death_year_match(self, year):
        """ Match the death year of an individual.  Year is an integer. """
        return self.death_year() == year

    def death_range_match(self, year1, year2):
        """ Check if the death year of an individual is in a given range.
        Years are integers.
        """
        year = self.death_year()
        if year1 <= year <= year2:
            return True
        return False

    def name(self):
        """ Return a person's names as a tuple: (first,last) """
        first = ""
        last = ""
        if not self.is_individual():
            return (first, last)
        for child in self.children():
            if child.tag() == "NAME":
                # some older Gedcom files don't use child tags but instead
                # place the name in the value of the NAME tag
                if child.value() != "":
                    name = child.value().split('/')
                    if len(name) > 0:
                        first = name[0].strip()
                        if len(name) > 1:
                            last = name[1].strip()
                else:
                    for childOfChild in child.children():
                        if childOfChild.tag() == "GIVN":
                            first = childOfChild.value()
                        if childOfChild.tag() == "SURN":
                            last = childOfChild.value()
        return (first, last)

    def gender(self):
        """ Return the gender of a person in string format """
        gender = ""
        if not self.is_individual():
            return gender
        for child in self.children():
            if child.tag() == "SEX":
                gender = child.value()
        return gender

    def private(self):
        """ Return if the person is marked private in boolean format """
        private = False
        if not self.is_individual():
            return private
        for child in self.children():
            if child.tag() == "PRIV":
                private = child.value()
                if private == 'Y':
                    private = True
        return private

    def birth(self):
        """ Return the birth tuple of a person as (date,place) """
        date = ""
        place = ""
        source = ()
        if not self.is_individual():
            return (date, place, source)
        for child in self.children():
            if child.tag() == "BIRT":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date = childOfChild.value()
                    if childOfChild.tag() == "PLAC":
                        place = childOfChild.value()
                    if childOfChild.tag() == "SOUR":
                        source = source + (childOfChild.value(),)
        return (date, place, source)

    def birth_year(self):
        """ Return the birth year of a person in integer format """
        date = ""
        if not self.is_individual():
            return date
        for child in self.children():
            if child.tag() == "BIRT":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date_split = childOfChild.value().split()
                        date = date_split[len(date_split) - 1]
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
        source = ()
        if not self.is_individual():
            return (date, place)
        for child in self.children():
            if child.tag() == "DEAT":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date = childOfChild.value()
                    if childOfChild.tag() == "PLAC":
                        place = childOfChild.value()
                    if childOfChild.tag() == "SOUR":
                        source = source + (childOfChild.value(),)
        return (date, place, source)

    def death_year(self):
        """ Return the death year of a person in integer format """
        date = ""
        if not self.is_individual():
            return date
        for child in self.children():
            if child.tag() == "DEAT":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        datel = childOfChild.value().split()
                        date = datel[len(datel) - 1]
        if date == "":
            return -1
        try:
            return int(date)
        except:
            return -1

    def burial(self):
        """ Return the burial tuple of a person as (date,place) """
        date = ""
        place = ""
        source = ()
        if not self.is_individual():
            return (date, place)
        for child in self.children():
            if child.tag() == "BURI":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date = childOfChild.value()
                    if childOfChild.tag() == "PLAC":
                        place = childOfChild.value()
                    if childOfChild.tag() == "SOUR":
                        source = source + (childOfChild.value(),)
        return (date, place, source)

    def census(self):
        """ Return list of census tuples (date, place) for an individual. """
        census = []
        if not self.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        for child in self.children():
            if child.tag() == "CENS":
                date = ''
                place = ''
                source = ''
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date = childOfChild.value()
                    if childOfChild.tag() == "PLAC":
                        place = childOfChild.value()
                    if childOfChild.tag() == "SOUR":
                        source = source + (childOfChild.value(),)
                census.append((date, place, source))
        return census

    def last_updated(self):
        """ Return the last updated date of a person as (date) """
        date = ""
        if not self.is_individual():
            return (date)
        for child in self.children():
            if child.tag() == "CHAN":
                for childOfChild in child.children():
                    if childOfChild.tag() == "DATE":
                        date = childOfChild.value()
        return (date)

    def occupation(self):
        """ Return the occupation of a person as (date) """
        occupation = ""
        if not self.is_individual():
            return (occupation)
        for child in self.children():
            if child.tag() == "OCCU":
                occupation = child.value()
        return occupation

    def deceased(self):
        """ Check if a person is deceased """
        if not self.is_individual():
            return False
        for child in self.children():
            if child.tag() == "DEAT":
                return True
        return False

    def get_individual(self):
        """ Return this element and all of its sub-elements """
        result = self.__unicode__()
        for child in self.children():
            result += child.get_individual()
        return result

    def __str__(self):
        if version_info[0] >= 3:
            return self.__unicode__()
        else:
            return self.__unicode__().encode('utf-8')

    def __unicode__(self):
        """ Format this element as its original string """
        if self.level() < 0:
            return ''
        result = str(self.level())
        if self.pointer() != "":
            result += ' ' + self.pointer()
        result += ' ' + self.tag()
        if self.value() != "":
            result += ' ' + self.value()
        result += self.__crlf
        return result
