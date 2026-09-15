#!/usr/bin/env python3
"""Generate the landing sitemap from the canonical URLs in its existing pages."""
from html.parser import HTMLParser
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

LANDING = Path(__file__).resolve().parents[1] / 'landing'

class CanonicalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.urls.append(attrs.get('href', ''))

def build(landing=LANDING):
    urls = set()
    for page in sorted(landing.rglob('*.html')):
        parser = CanonicalParser()
        parser.feed(page.read_text())
        if len(parser.urls) != 1:
            raise ValueError(f'{page}: expected one canonical URL')
        # The WAHS alias belongs to its own canonical subdomain.
        if parser.urls[0].startswith('https://openclinai.org/'):
            urls.add(parser.urls[0])
    tree = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for url in sorted(urls):
        SubElement(SubElement(tree, 'url'), 'loc').text = url
    return tostring(tree, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    (LANDING / 'sitemap.xml').write_bytes(build())
