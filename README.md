# recgov
A tool for viewing and working with data from [RIDB](https://ridb.recreation.gov/download)
and [recreation.gov](https://www.recreation.gov) (via its undocumented API).

## Install
Install [pipx](https://pipx.pypa.io/stable/) via Homebrew. Then run:

```bash
pipx install git+ssh://git@github.com/dtillery/recgov.git
```

After install, you will likely want to initialize the database and load entity data:

```bash
recgov init
```

Data is stored based on [platformdirs](https://github.com/platformdirs/platformdirs). On
a Mac it will likely be located at `~/Library/Application\ Support/recgov`.

### Upgrade
```bash
pipx reinstall recgov
```

This will not clear the database.

## Configuration
There's not much configuration right now to speak of.

### Environment Variables
I recommend managing these locally with like [direnv](https://direnv.net).

#### `RECGOV_ENV`
If this is set to `dev`, the entity CSVs and database will be saved in the package's
`data/` directory. Useful if you're doing development and want to inspect the database
easily.

## Usage
All subcommands are accessible under the `recgov` command. All support `--help` to list
documentation.

### `init [OPTIONS]`
Initializes the database (SQLite) and loads initial entity data. Most of this will come
from a zipfile of CSVs downloaded from RIDB while some will be retrieved directly from
the Rec.gov API. The relevant CSVs will remain stored locally after the first `init`,
and can be used instead of re-downloading with the addition of the `--skip-download` flag.

***This will not work with a previously initialized/populated database; it must be done
fresh or after a `drop`.***

Initial RIDB entities loaded include:

* Organizations
* Recreation Areas
* Facilities

Initial Rec.gov entities loaded include:

* Lotteries

```bash
# initialize with downloads
>> recgov init
...
# initialize with cached data
>> recgov init --skip-download
```

### `drop`
Completely drop the database and all contents. This will ask for y/n confirmation before
commencing.

### `load-divisions PERMIT_ID`
Retrieve and persist all divisions for a given Permit (aka a Facility) based on the Rec.gov
ID (**not** the internal DB id). This is only to save general information about each division,
and does not include any availability (date) information.

***This will not update a previously populated database; it must be done
fresh or after a `drop`.***

```bash
# load divisions for Glacier National Park Wilderness Permits
>> recgov load-divisions 4675321
```

### `list-permits SEARCH_SUBSTRING`
Print all Facilities of type "permit" with relevant information. Optionally provide a
(currenlty single word) substring argument to filter results based on the permit's name.

```bash
# find all permits containing "rainier"
>> recgov list-permits rainier
Mount Rainier National Park Wilderness and Climbing Permits (4675317)
Rec Area: Mount Rainier National Park (MORA)
Org: National Park Service (NPS)
```

### `load-lotteries`
Retrieve and persist all currently available (not necessarily to enter) lotteries from
Rec.gov. These may be needed for other operations and should be loaded automatically on
`init`

***This will not work with a previously initialized/populated database; it must be done
fresh or after a `drop`.***

```bash
recgov load-lotteries
```

### `list-lotteries SEARCH_SUBSTRING`
Print all lotteries with relevant information. Optionally provide a (currenlty single word)
substring argument to filter results based on the lottery's name or description.

```bash
# print lotteries with "cascade" in the name/desc.
>> recgov list-lotteries cascade
North Cascades 2024 Early Access Lottery: North Cascades National Park Backcountry Permits
UUID: 93d4020b-a326-431e-b3fa-54ea07bd45b7
Facility: North Cascades National Park Backcountry Permits (4675322)
Status: Executed
Open From: 3/4/24 => 3/16/24
Winners Access From: 3/25/24 => 4/23/24
```

### `create-itinerary PERMIT_ID ITINERARY_NAME`
Create a new itinerary with a given `ITINERARY_NAME` for a provided `PERMIT_ID`. The
`PERMIT_ID` corresponds to the Rec.gov id for a Facility with the type Permit. If no divisions
are found for the permit in the DB, you are given the option to retrieve them and continue.

Divisions can be chosen by typing at the prompt which will present matching autocomplete options.
Manually choosing the full autocomplete option or just confirming current search string
(assuming it matches only one option) will add the division to the itinerary. In addition
there are three other commands:

* `save`: Save the itinerary as it is.
* `cancel` (or ctrl+c): Cancel and disgard the itinerary.
* `list`: List all of the available divisions.

```bash
# create an itinerary in the North Cascades
>> recgov create-itinerary 4675322 northcascades
No divisions found for permit "North Cascades National Park Backcountry Permits". Load? [y/N]: y
Loading Divisions: 100%|█████████████████████████████████████████████████████████████████████████| 247/247 [00:00<00:00, 5908.95divs/s]
Begin typing and make a selection to add it to your itinerary.
=> "save" to save itinerary as currently constructed
=> "cancel" to exit without saving the current itinerary
=> "list" to list all division autocomplete options
? Choose a division: Pumpkin Mountain Camp
Adding Pumpkin Mountain Camp to the itinerary.
Current itinerary includes:
1. Pumpkin Mountain Camp
? Choose a division: save
Saving itinerary "northcascades" with stops:
1. Pumpkin Mountain Camp
```

### `list-itineraries`
List all of the existing itineraries all with their divisions (in order) and associated permit.

```bash
>> recgov list-itineraries
gunsightpass (Glacier National Park Wilderness Permits)
1. GUN - Gunsight Lake (No Campfires)
2. ELL - Lake Ellen Wilson (No Campfires)
3. SPE - Sperry (No Campfires)
```

### `find-itinerary-dates [OPTIONS] ITINERARY_NAME`
For a given itinerary, find all currenlty available reservation-date options on Rec.gov
for a given timeframe. At the start you may be asked to choose a related Lottery, as this
can affect the options available. Can/must be supplied with the following options:

* `-s YYYY-MM-DD` (required): the starting date to being searching from.
* `-e YYYY-MM-DD` (required): the ending date to search to.
* `-r` (optional): Flag to search for available dates for the itinerary in the reversed order.

```bash
# find available date options for the blueglacier Itinerary in June
>> recgov find-itinerary-dates -s 2024-06-01 -e 2024-06-30 blueglacier
4 date matches found:
Sat, Jun 15 - Mon, Jun 17
6/15/24: Lewis Meadow
6/16/24: Martin Creek
6/17/24: Happy Four
Fri, Jun 21 - Sun, Jun 23
6/21/24: Lewis Meadow
6/22/24: Martin Creek
6/23/24: Happy Four
Sun, Jun 23 - Tue, Jun 25
6/23/24: Lewis Meadow
6/24/24: Martin Creek
6/25/24: Happy Four
Mon, Jun 24 - Wed, Jun 26
6/24/24: Lewis Meadow
6/25/24: Martin Creek
6/26/24: Happy Four
```

## Terminology
Terms used here are often based on their counterparts from RIDB and Rec.gov. While some
attempts and using more "friendly" language have been made, often the underlying models
are opaque (especially from Rec.gov which is not documented) and hard to fully understand
when stumbling around from endpoint to endpoint. You can see how the government defines
some of these [here](https://ridb.recreation.gov/docs). Below are some of the most common
terms and their "meaning" as far as we're concerned.

### Organization
The government organization (federal and/or state) that manages the various parent entities.
Of note, there exists an Organization with ID 157 that does not appear in RIDB
Organization-exports but is referenced in other entities. Considering that many
Departments of X refer to it as their ParentOrg, I am going to assume it's equivalent to
the US Government for our purposes.

### Recreation Area
Areas of recreation! Refers to National Parks, Forests, Monuments, Trails, Refuges, and
many other types too numerous to mention.

### Facility
"Points of interest" within a recreation area. Can range from campgrounds to wilderness
permits to visitor centers to fish hatcheries. This is one of the most overloaded terms and
one I try to obfuscate often (e.g. refering to "permits" when creating itineraries). See
`recgov.models.facility.FacilityType` for all of the types we've encountered.

### Division
Appears to refer to indivial components that might make up an itinerary on Rec.gov. While
this is often associated with "campsites" (such as for wilderness permits), it can also
mean something like a zone you are entering at a specific date (for example, the Core Zone
in the Enchantments). It essentially seems like the idea was that many things can be divided
up, and therefore those parts are "divisions".
