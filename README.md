# recyoself
A tool for viewing and working with data from [RIDB](https://ridb.recreation.gov/download)
and [recreation.gov](https://www.recreation.gov) (via its undocumented API).

## Install
Install [pipx](https://pipx.pypa.io/stable/) via Homebrew. Then run:

```bash
pipx install git+ssh://git@github.com/dtillery/recyoself.git
```

After install, you will likely want to initialize the database and load entity data:

```bash
recyoself init
```

Data is stored based on [platformdirs](https://github.com/platformdirs/platformdirs). On
a Mac it will likely be located at `~/Library/Application\ Support/recyoself`.

### Upgrade
```bash
pipx reinstall recyoself
```

This will not clear the database.

## Configuration
There's not much configuration right now to speak of.

### Environment Variables
I recommend managing these locally with like [direnv](https://direnv.net).

#### `RECYOSELF_ENV`
If this is set to `dev`, the entity CSVs and database will be saved in the package's
`data/` directory. Useful if you're doing development and want to inspect the database
easily.

## Usage
All subcommands are accessible under the `recyoself` command. All support `--help` to list
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
>> recyoself init
...
# initialize with cached data
>> recyoself init --skip-download
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
>> recyoself load-divisions 4675321
```

### `list-facilities [OPTIONS] SEARCH_SUBSTRING`
Print all Facilities of type "permit" with relevant information. Optionally provide a
`--type` argument one or multiple times to filter facilities by their type (see FacilityType
for options). Optionally provide a (currenlty single word) substring argument to filter
results based on the permit's name.

```bash
# find all permits and campgrounds containing "rainier"
>> recyoself list-facilities --type permit --type campground glacier
Campground: Exit Glacier Campground (248555)
Rec Area: Kenai Fjords National Park (KEFJ)
Org: National Park Service (NPS)
...
Permit: Glacier National Park Wilderness Permits (4675321)
Rec Area: Glacier National Park (GLAC)
Org: National Park Service (NPS)
```

### `load-lotteries`
Retrieve and persist all currently available (not necessarily to enter) lotteries from
Rec.gov. These may be needed for other operations and should be loaded automatically on
`init`

***This will not work with a previously initialized/populated database; it must be done
fresh or after a `drop`.***

```bash
recyoself load-lotteries
```

### `list-lotteries SEARCH_SUBSTRING`
Print all lotteries with relevant information. Optionally provide a (currenlty single word)
substring argument to filter results based on the lottery's name or description.

```bash
# print lotteries with "cascade" in the name/desc.
>> recyoself list-lotteries cascade
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
>> recyoself create-itinerary 4675322 northcascades
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
>> recyoself list-itineraries
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
* `-e YYYY-MM-DD` (optional): the ending date to search to. If none is specified, the start
date will be used (i.e. single day trip start).
* `-r` (optional): Flag to search for available dates for the itinerary in the reversed order.
* `-l` (optional): A Lottery UUID to be used in place of asking for user input if multiple
lotteries are found for a facility (to facilitate daemon-mode)
* `--daemon-mode` (optional): Only print output if availabilities are found (to facilitate
running as a daemonized-script and running actions based on results).

```bash
# find available date options for the blueglacier Itinerary in June
>> recyoself find-itinerary-dates -s 2024-06-01 -e 2024-06-30 blueglacier
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

### `find-campsite-dates [OPTIONS] CAMPGROUND_ID NUM_DAYS`
For a given Campground (Facility) ID, find all starting dates for a reservation of length
NUM_DAYS. Options include:

* `-s, --start-date`: The day to start searching for reservation blocks. This is always required.
* `-e, --end-date`: The last day to search for a reservation blocks. This is optional, and
if it is not supplied only the given start-date will be used.
* `--include-nyr`: Include campsites that are Not Yet Reservable (but may become so at a
later date) in the results.
* `--daemon-mode` (optional): Only print output if availabilities are found (to facilitate
running as a daemonized-script and running actions based on results).

```bash
>> recyoself find-campsite-dates -s 2024-09-01 -e 2024-09-30 --include-nyr 247592 2
Hoh Rainforest Campground: 2-day availabilities from Sep 1 to Sep 30)
Site 1 (A): Standard, Non-Electric, starting on:
Wed, Sep 11
Sun, Sep 15
Mon, Sep 16
Tue, Sep 17
Wed, Sep 18
Site 32 (A): Standard, Non-Electric, starting on:
Tue, Sep 17
Site 39 (B): Standard, Non-Electric, starting on:
Sun, Sep 1 (NYR)
Mon, Sep 2 (NYR)
...
```

### `make_launchd_configs [OPTIONS] OUTPUT_DIR`
Make config for a launchd service based on provided options. I'll add more here when I get
around to confirming this actually works appropriately.

## Daemon Mode
Some command support a `--daemon-mode`. This configures the command to only print output
if there are availabilties are found. This is to facilitate running the commands as a part
of daemonized-scripts that are configured to alert based on results. Examples and
templates for setting this up can be found in the `daemon` directory.

Daemonization can be built around running the `run-and-alert.sh` script, which will run
a command (that should use the `--daemon-mode` option) and email a configured address if
results are found. This script relies on the [Himalaya 1.0.0](https://pimalaya.org/himalaya/cli/latest/)
library to perform email (see their setup instructions for getting started).

The commands that currently support this are:

* `find-itinerary-dates`
* `find-campsite-dates`

### Environment Variables
These environment variables are used in the `run-and-alert.sh` script.

* `PATH`: Path configuration for the script to run under (useful if you don't want to specify full paths to your commands)
* `RECYOSELF_DAEMON_CMD`: the recyoself command (in case it is aliased or a full path is necessary)
* `RECYOSELF_DAEMON_CMD_ARGS`: complete arguments passed to recyoself (e.g. `find-itinerary-dates ...`)
* `RECYOSELF_DAEMON_NOTIFY_NAME`: Appears in email subject after "Recyoself Alert:"
* `RECYOSELF_DAEMON_EMAIL`: the email address used as the `to` and `from` for Himalaya

### launchd
[launchd](https://www.launchd.info) is a cron-like service that comes with MacOS. While the computer not asleep it will
work as its schedule is configured. It can also function while the computer is asleep as
long as "Power Nap" is active, but running may be inconsistent (as it is at the whims of
however Power Nap works)

#### Installation
Configure `launchd/com.recyoself.daemon.cmd.plist.template` as required. Then copy it to
the LaunchAgents folder:

```bash
cp com.recyoself.daemon.your-cmd.plist ~/Library/LaunchAgents
```

#### Usage
Activate the daemon for running:

```bash
launchctl bootstrap gui/`id -u` ~/Library/LaunchAgents/com.recyoself.daemon.your-cmd.plist
```

Deactivate the daemon:

Activate the daemon for running:
```bash
launchctl bootout gui/`id -u` ~/Library/LaunchAgents/com.recyoself.daemon.your-cmd.plist
```

## TODO

- [ ] See if `caffeinate` or `pmset` would help with making running during power-nap more
consistent
- [ ] Refactor cli commands into multiple files
- [ ] Make sure `make-launchd-configs` works correctly

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
`recyoself.models.facility.FacilityType` for all of the types we've encountered.

### Division
Appears to refer to indivial components that might make up an itinerary on Rec.gov. While
this is often associated with "campsites" (such as for wilderness permits), it can also
mean something like a zone you are entering at a specific date (for example, the Core Zone
in the Enchantments). It essentially seems like the idea was that many things can be divided
up, and therefore those parts are "divisions".

### Campsite
Campsites that belong to a Facility. Can be car-camping, cabin, tents, boat-in, etc. There
are many different types and often have "GROUP" and "ELECTRIC"/"NONELECTRIC" variants.
Currently here are the types we've seen:

* `ANCHORAGE`
* `BALL FIELD`
* `BOAT IN`
* `CABIN ELECTRIC`
* `CABIN NONELECTRIC`
* `Designated Campsite`
* `EQUESTRIAN ELECTRIC`
* `EQUESTRIAN NONELECTRIC`
* `GROUP EQUESTRIAN`
* `GROUP HIKE TO`
* `GROUP PICNIC AREA`
* `GROUP RV AREA NONELECTRIC`
* `GROUP SHELTER ELECTRIC`
* `GROUP SHELTER NONELECTRIC`
* `GROUP STANDARD AREA ELECTRIC`
* `GROUP STANDARD AREA NONELECTRIC`
* `GROUP STANDARD ELECTRIC`
* `GROUP STANDARD NONELECTRIC`
* `GROUP TENT ONLY AREA NONELECTRIC`
* `GROUP WALK TO`
* `HIKE TO`
* `LOOKOUT`
* `MANAGEMENT`
* `MOORING`
* `OVERNIGHT SHELTER ELECTRIC`
* `OVERNIGHT SHELTER NONELECTRIC`
* `PARKING`
* `PICNIC`
* `RV ELECTRIC`
* `RV NONELECTRIC`
* `SHELTER ELECTRIC`
* `SHELTER NONELECTRIC`
* `STANDARD ELECTRIC`
* `STANDARD NONELECTRIC`
* `TENT ONLY ELECTRIC`
* `TENT ONLY NONELECTRIC`
* `WALK TO`
* `YES`
* `YURT`
* `Zone`
* ` ` (empty)
