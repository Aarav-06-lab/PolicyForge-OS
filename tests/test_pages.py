from html.parser import HTMLParser
from pathlib import Path
import unittest

class PageParser(HTMLParser):
    def __init__(self):super().__init__();self.ids=set();self.select=None;self.modes=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):self.ids.add(a['id'])
        if tag=='select':self.select=a.get('id')
        if tag=='option' and self.select=='tutorMode':self.modes.append(a)
    def handle_endtag(self,tag):
        if tag=='select':self.select=None

class PageStructureTests(unittest.TestCase):
    def test_tutor_has_two_real_mode_options(self):
        p=PageParser();p.feed((Path(__file__).resolve().parents[1]/'web/tutor.html').read_text())
        self.assertEqual([o.get('value') for o in p.modes],['local','generative'])
        self.assertIn('generativeOption',p.ids)
        self.assertEqual(p.modes[1]['id'],'generativeOption')

    def test_pages_have_unique_ids(self):
        class Unique(PageParser):
            def handle_starttag(self,tag,attrs):
                ident=dict(attrs).get('id')
                if ident and ident in self.ids:raise AssertionError('Duplicate ID: '+ident)
                super().handle_starttag(tag,attrs)
        for file in ['index.html','tutor.html','about.html']:
            p=Unique();p.feed((Path(__file__).resolve().parents[1]/'web'/file).read_text())
