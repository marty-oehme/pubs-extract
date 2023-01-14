# pubs-extract

[![status-badge](https://ci.martyoeh.me/api/badges/Marty/pubs-extract/status.svg)](https://ci.martyoeh.me/Marty/pubs-extract)
![PyPI](https://img.shields.io/pypi/v/pubs-extract)

Quickly extract annotations from your pdf files with the help of the pubs bibliography manager.
Easily organize your highlights and thoughts next to your documents.

## Installation:

You can install from pypi with `pip install pubs-extract`.

Or you install manually by moving the `extract` directory into your pubs `plugs` directory,
so that the hierarchy is `pubs/plugs/extract/`

Then add `extract` to your plugin list in the pubs configuration file:

```ini
[plugins]
active = extract
```

To check if everything is working you can do `pubs --help` which should show you the new extract command.
You will be set up with the default options but if you want to change anything, read on in configuration below.

> **Note**
> This plugin is in fairly early development. It does what I need it to do, but if you have a meticulously organized library *please* make backups before doing any operation on your notes, or make use of the pubs-included git plugin.

## Configuration:

In your pubs configuration file:

```ini
[plugins]
active = extract

[[extract]]
on_import = False
short_header = False
minimum_text_similarity = 0.75
minimum_color_similarity = 0.833
formatting = "{%quote_container> {quote} %}[{page}]{%note_container{newline}Note: {note} %}{%tag_container #{tag}%}"
```

If `on_import` is `True` extraction is automatically run whenever a new document is added to the library,
if false extraction has to be handled manually.

---

`short_header` determines if the headline of each annotation output (displaying the paper it is from) should contain the whole formatted author, year, title string (`False`) or just the citekey (`True`).

---

`minimum_text_similarity` sets the required similarity of an annotation's note and written words to be viewed
as one. Any annotation that has both and is *under* the minimum similarity will be added in the following form:

```markdown
> [13] my annotation
Note: my additional thoughts
```

That is, the extractor detects additional written words by whoever annotated and adds them to the extraction.
The option generally should not take too much tuning, but it is there if you need it.

---

`minimum_color_similarity` sets the required similarity of highlight/annotation colors to be recognized as the 'pure' versions of themselves for color mapping (see below). With a low required similarity, for example dark green and light green will both be recognized simply as 'green' while a high similarity will not match them, instead only matching closer matches to a pure (0, 255, 0) green value.

This should generally be an alright default but is here to be changed for example if you work with a lot of different annotation colors (where dark purple and light purple get different meanings) and get false positives.

---

The plugin contains a configuration sub-category of `tags`: Here, you can define meaning for your highlight/annotation colors. For example, if you always highlight the main arguments and findings in orange and always highlight things you have to follow up on in blue, you can assign the meanings 'important' and 'todo' to them respectively as follows:

```ini
[[[tags]]]
orange = "important"
blue = "todo"
```

Currently recognized colors are: `red` `green` `blue` `yellow` `purple` `orange`.
Since these meanings are often highly dependent on personal organization and reading systems,
no defaults are set here.

---

`formatting` takes a string with a variety of template options. You can use any of the following:

- `{page}`: The page number the annotation was found on.
- `{quote}`: The actual quoted string (i.e. highlighted).
- `{note}`: The annotation note (i.e. addded reader).
- `{%quote_container [other text] %}`: Mark the area that contains a quotation. Useful to get rid of prefixes or suffixes if no quotation exists. Usually contains some plain text and a `{quote}` element. Can *not* be nested with other containers.
- `{%note_container [other text] %}`: Mark the area that contains a note. Useful to get rid of prefixes or suffixes if no note exists. Usually contains some plain text and a `{note}` element. Can *not* be nested with other containers.
- `{%tag_container [other text] %}`: Mark the area that contains a tag. Useful to get rid of prefixes or suffixes if no tag exists. Usually contains some plain text and a `{tag}` element. Can *not* be nested with other containers.
- `{newline}`: Add a line break in the resulting annotation display.

For example, the default formatting string `"{%quote_container> {quote} %}[{page}]{%note_container{newline}Note: {note} %}{%tag_container #{tag}%}"` will result in this output:

```
> Mobilizing the TPSN scheme (see above) and drawing on cultural political economy and critical governance studies, this landmark article offers an alternative account [5]
Note: a really intersting take on polydolywhopp
```

Container marks are useful to encapsulate a specific type of the annotation, so extracted annotations in the end don't contains useless linebreaks or quotations markup.

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

**PLEASE** Heed the note above and exercise caution with the `-w` option. It is
not intended to be destructive, but nevertheless create backups or version
control your files.

You can invoke the command with `-e` to instantly edit the notes in your editor:

```bash
pubs extract -w -e Bayat2015 Peck2004
```

Will create/append annotations and drop you into the Bayat2015 note, when you
close it directly into the Peck2004 note. Take care that it will be fairly
annoying if you use this option with hundreds of entries being annotated as it
will open one entry after another for editing.

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

A note on the extraction: Highlights in pdfs can be somewhat difficult to parse
(as are most things in them). Sometimes they contain the selected text that is written on the
page, sometimes they contain the annotators thoughts as a note, sometimes they contain nothing.
This plugin makes an effort to find the right combination and extract the written words,
as well as any additional notes made - but things *will* slip through or extract weirdly every now
and again.

The easiest extraction is provided if your program writes the selection itself into the highlight
content, because then we can just use that. It is harder to parse if it does not and will sometimes
get additional words in front or behind (especially if the highlight ends in the middle of a line)
or even cut a few off.

I am not sure if there is much I can do about this.

---

If you spot a bug or have an idea feel free to open an issue.\
I might be slow to respond but will consider them all!

Pull requests are warmly welcomed.\
If they are big changes or additions let's talk about them in an issue first.

Thanks for using my software ❤️
