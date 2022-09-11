import calendar
import re
from datetime import datetime

months = [
    (None,),
    ("January", "Jan"),
    ("February", "Feb"),
    ("March", "Mar"),
    ("April", "Apr"),
    ("May",),
    ("June", "Jun"),
    ("July", "Jul"),
    ("August", "Aug"),
    ("September", "Sep", "Sept"),
    ("October", "Oct"),
    ("November", "Nov"),
    ("December", "Dec")
]

class Birthday:
    def __init__(self, month, day, year=None):
        self.month = month
        self.day = day
        self.year = year
        self.hasAge = self.year is not None

    def __repr__(self):
        if self.hasAge:
            return "{} {}, {}".format(months[self.month][0], self.day, self.year)
        return "{} {}".format(months[self.month][0], self.day)


number_regex = r"^(0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])([-/]\d+)?$"
word_regex = r"^\w+ (0?[1-9]|[12][0-9]|3[01])(, \d+)?$"

def parse_birthday(birthday: str):
    print("Attempting to parse birthday string: \"{}\"".format(birthday))

    if re.match(number_regex, birthday):
        print("Matched number regex!")
        objects = re.split(r"[-/]", birthday)
        month = int(objects[0])
        day = int(objects[1])
        if (len(objects) > 2):
            year = int(objects[2])

            if len(objects[2]) == 2:
                curr_year = datetime.utcnow().date().year
                curr_low_year = int(curr_year/100)*100
                
                year_dif = curr_year - curr_low_year # 20

                if year > year_dif:
                    year += curr_low_year-100
                else:
                    year += curr_low_year

        else:
            year = None

        return _get_bday_if_valid(month, day, year)

    if re.match(word_regex, birthday):
        print("Matched word regex!")
        objects = re.split(r",?\s", birthday)
        try:
            month = None
            for i in range(1, len(months)):
                if objects[0] in months[i]:
                    month = i
                    break
            if month is None:
                print ("Month {} invalid!")
                return None
        except:
            print ("Month {} invalid!")
            return None
        day = int(objects[1])

        if (len(objects) > 2):
            year = int(objects[2])
        else:
            year = None

        return _get_bday_if_valid(month, day, year)

    print("No regex matched, returning none.")
    return None


def _get_bday_if_valid(month, day, year):
    
    if year is not None and year > datetime.utcnow().date().year:
        print(f"Year {year} is more than the current year!")
        return None

    if year is None and (day > calendar.mdays[month] or (month is 2 and day is not 29)):
        print(f"Day {day} out of range for month {month}")
        return None
    
    if year is not None and day > calendar.monthrange(year, month)[1]:
        print(f"Day {day} out of range for month {month}, {year}")
        return None
    

    
    birthday : Birthday = Birthday(month, day, year)

    if birthday.hasAge and get_age(birthday) < 0:
        return None

    return birthday


def get_age(birthday: Birthday):
    curr_date = datetime.utcnow().date()
    
    year_diff = curr_date.year - birthday.year

    if curr_date.month < birthday.month or (curr_date.month == birthday.month and curr_date.day < birthday.day):
        year_diff -= 1
    
    return year_diff