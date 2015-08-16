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
        self.__element_top = Element(-1, "", "TOP", "")
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
        gedcom_file = open(filepath, 'rU')
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
            '( [^\n\r]*|)' +
            # End of line defined by \n or \r
            '(\r|\n)'
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
        element = Element(level, pointer, tag, value)
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

    # Methods for analyzing individuals and relationships between individuals

    def marriages(self, individual):
        """ Return list of marriage tuples (date, place) for an individual. """
        marriages = []
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        fams_families = self.families(individual, "FAMS")
        for family in fams_families:
            for famdata in family.children():
                if famdata.tag() == "MARR":
                    for marrdata in famdata.children():
                        date = ''
                        place = ''
                        if marrdata.tag() == "DATE":
                            date = marrdata.value()
                        if marrdata.tag() == "PLAC":
                            place = marrdata.value()
                        marriages.append((date, place))
        return marriages

    def marriage_years(self, individual):
        """ Return list of marriage years (as int) for an individual. """
        dates = []
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        fams_families = self.families(individual, "FAMS")
        for family in fams_families:
            for famdata in family.children():
                if famdata.tag() == "MARR":
                    for marrdata in famdata.children():
                        if marrdata.tag() == "DATE":
                            date = marrdata.value().split()[-1]
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
            if year >= year1 and year <= year2:
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
        for child in individual.children():
            is_fams = (child.tag() == family_type and
                       child.value() in self.__element_dict and
                       self.__element_dict[child.value()].is_family())
            if is_fams:
                families.append(self.__element_dict[child.value()])
        return families

    def get_ancestors(self, indi, anc_type="ALL"):
        """ Return elements corresponding to ancestors of an individual

        Optional anc_type. Default "ALL" returns all ancestors, "NAT" can be
        used to specify only natural (genetic) ancestors.
        """
        if not indi.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = self.get_parents(indi, anc_type)
        ancestors = parents
        for parent in parents:
            ancestors = ancestors + self.get_ancestors(parent)
        return ancestors

    def get_parents(self, indi, parent_type="ALL"):
        """ Return elements corresponding to parents of an individual
        
        Optional parent_type. Default "ALL" returns all parents. "NAT" can be
        used to specify only natural (genetic) parents. 
        """
        if not indi.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = []
        famc_families = self.families(indi, "FAMC")
        for family in famc_families:
            if parent_type == "NAT":
                for famrec in family.children():
                    if famrec.tag() == "CHIL" and famrec.value() == indi.pointer():
                        for chilrec in famrec.children():
                            if chilrec.value() == "Natural":
                                if chilrec.tag() == "_FREL":
                                    parents = (parents + 
                                               self.get_family_members(family, "WIFE"))
                                elif chilrec.tag() == "_MREL":
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
        family_members = [ ]
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
            if is_family and elem.value() in self.__element_dict:
                family_members.append(self.__element_dict[elem.value()])
        return family_members

    # Other methods

    def print_gedcom(self):
        """Write GEDCOM data to stdout."""
        for element in self.element_list():
            print(element)


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

    def __init__(self,level,pointer,tag,value):
        """ Initialize an element.  
        
        You must include a level, pointer, tag, and value. Normally 
        initialized by the Gedcom parser, not by a user.
        """
        # basic element info
        self.__level = level
        self.__pointer = pointer
        self.__tag = tag
        self.__value = value
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
                    name = e.value().split('/')
                    if len(name) > 0:
                        first = name[0].strip()
                        if len(name) > 1:
                            last = name[1].strip()
                else:
                    for c in e.children():
                        if c.tag() == "GIVN":
                            first = c.value()
                        if c.tag() == "SURN":
                            last = c.value()
        return (first,last)

    def gender(self):
        """ Return the gender of a person in string format """
        gender = ""
        if not self.is_individual():
            return gender
        for e in self.children():
            if e.tag() == "SEX":
                gender = e.value()
        return gender

    def private(self):
        """ Return if the person is marked private in boolean format """
        private = False
        if not self.is_individual():
            return gender
        for e in self.children():
            if e.tag() == "PRIV":
                private = e.value()
                if private == 'Y':
                    private = True
        return private

    def birth(self):
        """ Return the birth tuple of a person as (date,place) """
        date = ""
        place = ""
        source = ()
        if not self.is_individual():
            return (date,place,source)
        for e in self.children():
            if e.tag() == "BIRT":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
                    if c.tag() == "PLAC":
                        place = c.value()
                    if c.tag() == "SOUR":
                        source = source + (c.value(),)
        return (date,place,source)

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
        source = ()
        if not self.is_individual():
            return (date,place)
        for e in self.children():
            if e.tag() == "DEAT":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
                    if c.tag() == "PLAC":
                        place = c.value()
                    if c.tag() == "SOUR":
                        source = source + (c.value(),)
        return (date,place,source)

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

    def burial(self):
        """ Return the burial tuple of a person as (date,place) """
        date = ""
        place = ""
        source = ()
        if not self.is_individual():
            return (date,place)
        for e in self.children():
            if e.tag() == "BURI":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
                    if c.tag() == "PLAC":
                        place = c.value()
                    if c.tag() == "SOUR":
                        source = source + (c.value(),)
        return (date,place,source)

    def census(self):
        """ Return list of census tuples (date, place) for an individual. """
        census = []
        if not self.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        for pdata in self.children():
            if pdata.tag() == "CENS":
                date = ''
                place = ''
                source = ''
                for indivdata in pdata.children():
                    if indivdata.tag() == "DATE":
                        date = indivdata.value()
                    if indivdata.tag() == "PLAC":
                        place = indivdata.value()
                    if indivdata.tag() == "SOUR":
                        source = source + (indivdata.value(),)
                census.append((date, place, source))
        return census

    def last_updated(self):
        """ Return the last updated date of a person as (date) """
        date = ""
        if not self.is_individual():
            return (date)
        for e in self.children():
            if e.tag() == "CHAN":
                for c in e.children():
                    if c.tag() == "DATE":
                        date = c.value()
        return (date)

    def occupation(self):
        """ Return the occupation of a person as (date) """
        occupation = ""
        if not self.is_individual():
            return (date)
        for e in self.children():
            if e.tag() == "OCCU":
                occupation = e.value()
        return occupation

    def deceased(self):
        """ Check if a person is deceased """
        if not self.is_individual():
            return False
        for e in self.children():
            if e.tag() == "DEAT":
                return True
        return False

    def get_individual(self):
        """ Return this element and all of its sub-elements """
        result = str(self)
        for e in self.children():
            result += '\n' + e.get_individual()
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
