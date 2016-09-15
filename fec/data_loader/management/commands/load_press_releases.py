import glob
import json
import os
import logging

from dateutil import parser
from slugify import slugify

from django.utils import timezone
from django.core.management import BaseCommand

from home.models import PressReleasePage as prp
from home.models import Page


#### move to a another file
def strip_cruft(body):
    replacements = [
        # deletions - these are from the header and we don't need them as part of the content
        ('<body bgcolor="#FFFFFF">', ''),
        ('News Releases, Media Advisories<br/>', ''),
        ('<a href="http://www.fec.gov"><img src="../jpg/topfec.jpg" border="0" width="81" height="81" alt="FEC Home Page"/></a> </p>', ''),
        ("""width="100%""""", ''),
        ("""width="187""""", ''),
        ("""<h1>News Releases</h1>""", ''),
        # replacements
        ("""<p align="right"><b>Contact:</b></p>""",  """<p><b>Contact:</b></p>"""),
        ('Contact:', 'Contact: '),
        # neutering font for now will replace later
        ('face="Book Antiqua"', ''),
        (' size="1"', ''),
        (' size="2"', ''),
        (' size="3"', ''),
        (' size="0"', ''),
        (' size="-1"', ''),
        (' size="-2"', ''),
        (' size="-3"', ''),
        ('<p><a href="/">HOME</a> / <a href="/press/press.shtml">PRESS OFFICE</a><br/>', ''),
        ('News Releases, Media Advisories<br/>', ''),
        ('<a href="http://www.fec.gov"><img src="../jpg/topfec.jpg" border="0" width="81" height="81"/></a>', ''),
        ('<img src="../../../images/filetype-pdf.gif" alt="PDF" width="16" height="16" hspace="0" vspace="0" align="default"/>', ''),
        ('<a href="http://www.fec.gov"><img src="../jpg/topfec.jpg" border="0" width="81" height="81" alt="FEC Seal Linking to FEC.GOV"/></a>', ''),
        ('<img src="../../jpg/topfec.jpg" border="0" alt="FEC Home Page" width="81" height="81"/></a>', ''),
        ('<a href="http://www.fec.gov"><font><img src="../jpg/topfec.jpg" border="0"/></font></a>', ''),
        ('<a href="http://www.fec.gov"><img src="../jpg/topfec.jpg" border="0"/>', ''),
        ('<img src="../jpg/topfec.jpg" border="0" width="81" height="81"/>', ''),
        ('<img src="/jpg/topfec.jpg" ismap="ismap" border="0"/>', ''),
        # we got an ok to not have redundant content
        ('.pdf version of this news release', ''),
        ('bgcolor="#FFFFFF"', ''),
        ('color="#000000"', ''),
        ('text="#000000"', ''),
        ('link="#000099"', ''),
        ('vlink="#ff0000"', ''),
        ('alink="#FF0000">', ''),
        # In the 80s, they used pre to get spacing, but that kills the font in a bad way, I am adding some inline styling to perserve the spaces. It isn't perfect, but it is better.
        ('<pre>', '<div style="white-space: pre-wrap;">'),
        ('</pre>', '</div>'),
    ]
    for old, new in replacements:
        if not body:
            print("__WTF___")
        else:
            body = str.replace(body, old, new)
    # Flag
    if """You have performed a blocked operation""" in body:
        print('-----BLOCKED PAGE------')
    return body
###


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dirname = os.path.dirname
MAIN_DIRECTORY = dirname(dirname(dirname(__file__)))


def get_full_path(*path):
    return os.path.join(MAIN_DIRECTORY, *path)


def escape(text):
    # for loading into the db correctly
    escape_single = text.replace("'", "''")
    return escape_single


def validate_category(name):
    if name.lower() in [
        "audit reports",
        "campaign finance data summaries",
        "commission appointments",
        "disclosure initiatives",
        "enforcement matters",
        "hearings",
        "litigation",
        "non-filer publications",
        "open meetings and related matters",
        "presidential public funds",
        "rulemakings",
        "other agency actions",
    ]:
        return name.lower()
    else:
        return "other agency actions"


def add_page(item, base_page):
    item_year = parser.parse(item['date']).year
    title = item['title'][:255]
    category = validate_category(item['category'])
    slug = slugify(str(item_year) + '-' + category + '-' + title)[:225]
    url_path = "/home/media/" + slug + "/"

    # we need to load multiple times get rid of previous loads
    if Page.objects.filter(url_path=url_path).count() > 0:
        for p in Page.objects.filter(url_path=url_path):
            print(p)
            p.delete()
    body = escape(strip_cruft(item['html']))
    body_list = [{"value": body, "type": "html"}]
    formatted_body = json.dumps(body_list)
    publish_date = parser.parse(item['date'])

    press_page = prp(
        depth=4,
        numchild=0,
        title=title,
        live=1,
        has_unpublished_changes='0',
        url_path=url_path,
        seo_title=title,
        show_in_menus=0,
        search_description=title,
        category=category,
        expired=0,
        owner_id=1,
        locked=0,
        first_published_at=publish_date,
    )

    if prp.objects.filter(path=url_path).count() > 0:
        for p in prp.objects.filter(upath=url_path):
            p.delete()

    base_page.add_child(instance=press_page)
    saved_page = prp.objects.get(id=press_page.id)
    saved_page.body = formatted_body
    saved_page.first_published_at = publish_date
    latest_revision_created_at= publish_date
    saved_page.created_at = publish_date
    saved_page.date = publish_date
    saved_page.save()


def load_press_releases_from_json():
    """Loops through json files and adds them to wagtail"""
    # Base Page that the pages you are adding belong to
    base_page = Page.objects.get(url_path='/home/media/')

    paths = sorted(glob.glob('data_loader/data/pr_json/' + '*.json'))
    logger.info("starting...")
    for path in paths:
        print(path)
        with open(path, 'r') as json_contents:
            logger.info(path)
            contents = json.load(json_contents)
            if contents['title'] is None or contents['title'].isspace():
                # this seems to be the case for the PR docs
                contents['title'] = contents['category']

            add_page(contents, base_page)


class Command(BaseCommand):
    help = "loads press releases from json"

    def handle(self, *args, **options):
        load_press_releases_from_json()
