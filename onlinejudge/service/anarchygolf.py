# Python Version: 3.x
"""
the module for Anarchy Golf (http://golf.shinh.org/)
"""

import urllib.parse
from typing import *

import bs4
import requests

import onlinejudge._implementation.testcase_zipper
import onlinejudge._implementation.utils as utils
import onlinejudge.dispatch
import onlinejudge.type


class AnarchyGolfService(onlinejudge.type.Service):
    def get_url(self) -> str:
        return 'http://golf.shinh.org/'

    def get_name(self) -> str:
        return 'Anarchy Golf'

    @classmethod
    def from_url(cls, url: str) -> Optional['AnarchyGolfService']:
        # example: http://golf.shinh.org/
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'golf.shinh.org':
            return cls()
        return None


class AnarchyGolfProblem(onlinejudge.type.Problem):
    def __init__(self, *, problem_id: str):
        self.problem_id = problem_id

    def download_sample_cases(self, *, session: Optional[requests.Session] = None) -> List[onlinejudge.type.TestCase]:
        session = session or utils.get_default_session()
        # get
        resp = utils.request('GET', self.get_url(), session=session)
        # parse
        soup = bs4.BeautifulSoup(resp.text, utils.HTML_PARSER)
        samples = onlinejudge._implementation.testcase_zipper.SampleZipper()
        for h2 in soup.find_all('h2'):
            it = self._parse_sample_tag(h2)
            if it is not None:
                s, name = it
                samples.add(s.encode(), name)
        return samples.get()

    def _parse_sample_tag(self, tag: bs4.Tag) -> Optional[Tuple[str, str]]:
        assert isinstance(tag, bs4.Tag)
        assert tag.name == 'h2'
        name = tag.contents[0]
        if ':' in name:
            name = name[:name.find(':')]
        if name in ['Sample input', 'Sample output']:
            nxt = tag.next_sibling
            while nxt and nxt.string.strip() == '':
                nxt = nxt.next_sibling

            # This implementation is discussed in https://github.com/kmyk/online-judge-tools/pull/599
            if nxt.name == 'pre':
                s = utils.dos2unix(nxt.string[1:])
            elif nxt.name == 'p':
                s = ''  # *NOTHING* means that the empty string "" is input, not "\n".

            return s, name
        return None

    def get_url(self) -> str:
        return 'http://golf.shinh.org/p.rb?{}'.format(self.problem_id)

    def get_service(self) -> AnarchyGolfService:
        return AnarchyGolfService()

    @classmethod
    def from_url(cls, url: str) -> Optional['AnarchyGolfProblem']:
        # example: http://golf.shinh.org/p.rb?The+B+Programming+Language
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'golf.shinh.org' \
                and utils.normpath(result.path) == '/p.rb' \
                and result.query:
            return cls(problem_id=result.query)
        return None


onlinejudge.dispatch.services += [AnarchyGolfService]
onlinejudge.dispatch.problems += [AnarchyGolfProblem]
