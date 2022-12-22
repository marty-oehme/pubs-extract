# pubs-extract

Quickly extract annotations from your pdf files with the help of the pubs bibliography manager.

## Installation:

Still a bit painful since I have not set up any package management:

Put `extract` folder in your pubs `plugs` directory.

Then add `extract` to your plugin list in the pubs configuration file.

## Configuration:

In your pubs configuration file:

```ini
[plugins]
active = extract

[[extract]]
on_import = False
quote_prefix = "> "
note_prefix = "Note: "
minimum_similarity = 0.75
```

If `on_import` is `True` extraction is automatically run whenever a new document is added to the library,
if false extraction has to be handled manually.

`quote_prefix` and `note_prefix` define what is put in front of the quoted part of an annotation and the annotator's own notes respectively, so that ultimately a note (by default) looks like this:

```markdown
[4] > came “urban rights” caused collective outrage. Thus, through- out 2007 and 2008, protestors in towns and villages across the Nile Delta poured into the streets to rally over cuts in water flow. Deployment of massive riot police could not stop
Note: Often illegally connected to network, ‘revolution of the thirsty’
```

`minimum_similarity` sets the required similarity of an annotation's note and written words to be viewed
as one. Any annotation that has both and is *under* the minimum similarity will be added in the following form:

```markdown
> [13] my annotation
Note: my additional thoughts
```

That is, the extractor detects additional written words by whoever annotated and adds them to the extraction.
The option generally should not take too much tuning, but it is there if you need it.

## Usage:

`pubs extract [-h|-w|-e] <citekeys>`

For example, to extract annotations from two entries, do:

```bash
pubs extract Bayat2015 Peck2004
```

This will print the extracted annotations to the commandline through stdout.

If you invoke the command with the `-w` option, it will write it into your notes instead:

```bash
pubs extract -w Bayat2015 Peck2004
```

Will create notes for the two entries in your pubs note directory and fill them with
the annotations. If a note already exists for any of the entries, it will instead append
the annotations to the end of it, dropping all those that it already finds in the note
(essentially only adding new annotations to the end).

**PLEASE** Be aware that so far, I spent a single afternoon coding this plugin, it
contains no tests and operates on your notes. In my use nothing too bad happened but
only use it with adequate backup in place, or with your library being version controlled.

You can invoke the command with `-e` to instantly edit the notes:

```bash
pubs extract -w -e Bayat2015 Peck2004
```

Will create/append annotations and drop you into the Bayat2015 note, when you close it
directly into the Peck2004 note. Take care that it will be fairly annoying if you use this
option with hundreds of entries being annotated.

To extract the annotations for all your existing entries in one go, you can use:

```bash
pubs extract -w $(pubs list -k)
```

However, the warning for your notes' safety goes doubly for this command since it will touch
*most* or *all* of your notes, depending on how many entries in your library have pdfs attached.

This readme is still a bit messy, feel free to extend it and raise a PR if you have the time.

What follows is a not-very-sorted train of though on where the plugin is at and where I
could see myself taking it one day, provided I find the time.
Pull requests tackling one of these areas of course very welcome.

## Issues

A note on the extraction. Highlights in pdfs are somewhat difficult to parse
(as are most things in them). Sometimes they contain the selected text that is written on the
page, sometimes they contain the annotators thoughts as a note, sometimes they contain nothing.
This plugin makes an effort to find the right combination and extract the written words,
as well as any additional notes made - but things *will* slip through or extract weirdly every now
and again.

The easiest extraction is provided if your program writes the selection itself into the highlight
content, because then we can just use that. It is harder to parse if it does not.

## Roadmap:

- [x] extracts highlights and annotations from a doc file (e.g. using PyMuPDF)
- [ ] puts those in the annotation file of a doc in a customizable format
- [x] option to have it automatically run after a file is added?
    - option to have it run whenever a pdf in the library was updated?
- [ ] needs some way to delimit where it puts stuff and user stuff is in note
    - [ ] one way is to have it look at `> [17] here be extracted annotation from page seventeen` annotations and put it in between
    - [x] another, probably simpler first, is to just append missing annotations to the end of the note
- [ ] some highlights (or annotations in general) do not contain text as content
    - [ ] pymupdf can extract the content of the underlying rectangle (mostly)
    - [ ] issue is that sometimes the highlight contents are in content, sometimes a user comment instead
        - [ ] we could have a comparison function which estimates how 'close' the two text snippets are and act accordingly
- [ ] config option to map colors in annotations to meaning ('read', 'important', 'extra') in pubs
    - [ ] colors are given in very exact 0.6509979 RGB values, meaning we could once again estimate if a color is 'close enough' in distance to tag it accordingly
- [ ] make invoking the command run a query if corresponding option provided (or whatever) in pubs syntax and use resulting papers
    - [ ] confirm for many papers?
- [ ] warning when the amount of annotations in file is different than the amount extracted?

## Things that would also be nice in pubs in general and don't really belong in this repository

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
