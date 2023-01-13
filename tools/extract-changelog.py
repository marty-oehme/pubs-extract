import re

## Extracts the version and newest changes from a semantic changelog.
#
# Important, it only works with three-parted version numbers
# a-la 1.2.3 or 313.01.1888 -- needs \d.\d.\d to work.
#
# The version number and changeset will be put in `NEWEST_VERSION.md`
# and `NEWEST_CHANGES.md` respectively, for further use in releases.
OUTPUT_FILE_VERSION = "NEWEST_VERSION.md"
OUTPUT_FILE_CHANGES = "NEWEST_CHANGES.md"


def getVersion(file):
    for line in file:
        m = re.match(r"^## \[(\d+\.\d+\.\d+)\]", line)
        if m and m.group(1):
            return m.group(1)


def getSection(file):
    inRecordingMode = False
    for line in file:
        if not inRecordingMode:
            if re.match(r"^## \[\d+\.\d+\.\d+\]", line):
                inRecordingMode = True
        elif re.match(r"^## \[\d+\.\d+\.\d+\]", line):
            inRecordingMode = False
            break
        elif re.match(r"^$", line):
            pass
        else:
            yield line


def toFile(fname, content):
    file = open(fname, "w")
    file.write(content)
    file.close()


with open("CHANGELOG.md") as file:
    title = getVersion(file)
    print(title)
    toFile(OUTPUT_FILE_VERSION, title)

with open("CHANGELOG.md") as file:
    newest_changes_gen = getSection(file)
    newest_changes = ""
    for line in newest_changes_gen:
        newest_changes += line
    print("[Extracted Changelog]")
    print(newest_changes)
    toFile(OUTPUT_FILE_CHANGES, newest_changes)

file.close()
