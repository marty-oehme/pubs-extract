# pubs-extract

Quickly extract annotations from your pdf files with the help of the pubs bibliography manager.

Installation:

Put `extract` folder in your pubs `plugs` directory.

Add extract to your plugin list in pubs configuration file.

Usage:

`pubs extract <citekeys>`

This readme is a stub so far, feel free to extend it and raise a PR if you have the time.
What follows is a not-very-sorted train of though on the plugin and pubs in general,
to keep my thoughts in one place while I work on it.

## extractor plugin:

- extracts highlights and annotations from a doc file (e.g. using PyMuPDF)
- puts those in the annotation file of a doc in a customizable format
- option to have it automatically run after a file is updated?
- needs some way to delimit where it puts stuff and user stuff is in note
    - one way is to have it look at `> [17] here be extracted annotation from page seventeen` annotations and put it in between
    - another, probably simpler first, is to just append missing annotations to the end of the note
- some highlights (or annotations in general) do not contain text as content
    - pymupdf can extract the content of the underlying rectangle (mostly)
    - issue is that sometimes the highlight contents are in content, sometimes a user comment instead
        - we could have a comparison function which estimates how 'close' the two text snippets are and act accordingly
- config option to map colors in annotations to meaning ('read', 'important', 'extra') in pubs
    - colors are given in very exact 0.6509979 RGB values, meaning we could once again estimate if a color is 'close enough' in distance to tag it accordingly
- make invoking the command run a query if `-e` option provided (or whatever) in pubs syntax and use resulting papers
    - confirm?

# would also be nice in pubs, missing for me

- `show` command which simply displays given entry in a nice way
    - could take multiple entries but present them all in the same larger way
    - a metadata command which shows the metadata connected to an entry (e.g. `show --meta`)
- XDG compliance
    - a way to insert env vars into the configuration paths
    - looking in XDG_CONFIG_HOME and XDG_DATA_HOME by default
    - accepting env vars for overriding the directories
- isbn import re-enabled with -> `api.paperpile.com/api/public/convert`
    - example request: `curl -X POST -d '{"fromIds":true,"input":"9780816530441","targetFormat":"Bibtex"}' -H "Content-Type: application/json" https://api.paperpile.com/api/public/convert`
    - example reponse: `{"output":"@BOOK{Igoe2017-cu,\n  title     = \"The nature of spectacle\",\n  author    = \"Igoe, James\",\n  publisher = \"University of Arizona Press\",\n  series    = \"Critical Green Engagements: Investigating the Green Economy and\n               its Alternatives\",\n  month     =  jun,\n  year      =  2017,\n  address   = \"Tucson, AZ\",\n  language  = \"en\"\n}\n","token":"3ca6b666-2b9d-4962-8017-a0c8f1f86bfd","tags":[],"withErrors":false}`
- side-by-side command to open annotation file and document at the same time
- fzf-mode/bemenu mode to look through documents
- batch-edit? a way to quickly modify items matching a query, e.g. removing file entry for all those from year:2022 or whatever
- link related items
    - a special tag?
    - building relationships: two-way (related, e.g. same working paper), or single direction, e.g. a re-print, a compendium, etc
    - should still always be traceable from both sides
- automatically keeping a main bibtex file up-to-date
    - can be done through the `export` command, e.g. as a git hook when the repo is updated
- better git commit names for git plugin
- more direct linking to individual annotations
    - e.g. you have an annotation on page 17, allow opening that page from there and vice versa
    - can use e.g. existing markdown quote pattern:
      > [17] To be or not to be blabla
      which would then open page 17 in the document
    - makes most sense as plugin probably (which also allows setting the pattern by which it finds citations in the notes)
- fuzzy matching
    - either by default, as a config setting or with the ~prefix
- why are we doing tags in metadata not in the bibtex files?
- default replacement bibkey for files which are missing part of what makes it up
    - e.g. if you use {authorname}{year} as bibkey, a file missing author would substitute with this
